"""Local FastAPI surface for the offline trainer core.

The browser dashboard uses relative ``/api`` URLs. Every route operates on the
local SQLite database and never creates an outbound network client.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.adaptive import ScenarioOption, select_next_scenario, unit_summary, unit_trends
from core.api.runtime import LocalServices, create_local_services
from core.db import (
    AuthorizationError,
    BackupError,
    PinValidationError,
    Role,
    User,
    backup_sqlite_database,
    require_role,
    verify_pin,
)
from core.generator import (
    ScenarioGenerationError,
    ScenarioProfile,
    ScenarioV1Error,
    ScenarioV1Profile,
    ScenarioValidationError,
    generate_scenario,
    generate_scenario_v1,
)
from core.replay import replay_frame
from core.scoring import DoctrineValidationError, ScoringError
from core.sessions import EventConflictError, SessionManagerError


class CredentialsInput(BaseModel):
    user_id: str = Field(min_length=3, max_length=64)
    pin: str = Field(min_length=4, max_length=12)


class UserCreateInput(CredentialsInput):
    role: Literal["trainee", "instructor", "admin"]
    unit_id: str = Field(default="local-unit", min_length=3, max_length=64)


class ScenarioProfileInput(BaseModel):
    profile_id: str = Field(min_length=3, max_length=64)
    difficulty: int = Field(ge=1, le=5)
    skill_tags: list[str] = Field(min_length=1, max_length=16)


class GenerateV0Input(BaseModel):
    seed: int = Field(ge=0)
    profile: ScenarioProfileInput


class GenerateV1Input(BaseModel):
    seed: int = Field(ge=0)
    profile: ScenarioProfileInput
    swarm_size: int = Field(default=3, ge=2, le=16)
    clutter_count: int = Field(default=2, ge=0, le=16)
    terrain: Literal["abstract_flat", "rural", "urban"] = "rural"
    time_of_day: Literal["day", "night", "dawn_dusk"] = "day"
    weather: Literal["clear", "haze", "rain"] = "clear"


class SessionCreateInput(BaseModel):
    trainee_id: str = Field(min_length=3, max_length=64)
    scenario: dict[str, Any]
    session_id: str | None = None
    selection_mode: Literal["fixed", "adaptive"] = "fixed"


class EventInput(BaseModel):
    event: dict[str, Any]


class DoctrineUploadInput(BaseModel):
    yaml_text: str = Field(min_length=1, max_length=256_000)


class ScoreInput(BaseModel):
    doctrine_id: str = Field(min_length=3, max_length=64)
    version: str = Field(min_length=5, max_length=64)


class BackupInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class AdaptiveOptionInput(BaseModel):
    profile_id: str = Field(min_length=3, max_length=64)
    difficulty: int = Field(ge=1, le=5)
    skill_tags: list[str] = Field(min_length=1, max_length=16)


class AdaptiveSelectionInput(BaseModel):
    trainee_id: str = Field(min_length=3, max_length=64)
    options: list[AdaptiveOptionInput] = Field(min_length=1, max_length=32)


def create_app(
    services: LocalServices | None = None,
    *,
    dashboard_dir: Path | None = None,
) -> FastAPI:
    """Create a testable local-only app with an optional bundled dashboard."""
    local_services = services or create_local_services()
    app = FastAPI(
        title="SIH 26247 Offline Trainer API",
        version="0.8.0",
        description="Local-only training service. No telemetry or external service calls.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    def current_actor(
        x_actor_id: Annotated[str | None, Header()] = None,
        x_pin: Annotated[str | None, Header()] = None,
    ) -> str:
        """Authenticate every mutating/read API action against a local PIN hash."""
        if not x_actor_id or not x_pin:
            raise HTTPException(status_code=401, detail="X-Actor-Id and X-Pin headers are required")
        with local_services.session_factory() as db:
            user = db.get(User, x_actor_id)
            if user is None or not verify_pin(x_pin, user.pin_hash):
                raise HTTPException(status_code=401, detail="invalid local credentials")
        return x_actor_id

    @app.exception_handler(AuthorizationError)
    async def authorization_error(_: Request, error: AuthorizationError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(EventConflictError)
    async def event_conflict(_: Request, error: EventConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(SessionManagerError)
    @app.exception_handler(DoctrineValidationError)
    @app.exception_handler(ScenarioGenerationError)
    @app.exception_handler(ScenarioV1Error)
    @app.exception_handler(ScenarioValidationError)
    @app.exception_handler(ScoringError)
    @app.exception_handler(BackupError)
    @app.exception_handler(PinValidationError)
    async def domain_error(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str | bool]:
        return {"status": "ok", "stage": "8", "offline_only": True}

    @app.post("/api/bootstrap", tags=["auth"])
    def bootstrap(payload: CredentialsInput) -> dict[str, str]:
        """Create the first local admin and seed the generic demo doctrine once."""
        local_services.sessions.create_bootstrap_admin(payload.user_id, payload.pin)
        generic_path = Path(__file__).resolve().parents[2] / "doctrine" / "generic_demo.yaml"
        local_services.doctrines.upload(
            actor_id=payload.user_id,
            yaml_text=generic_path.read_text(encoding="utf-8"),
        )
        return {"user_id": payload.user_id, "role": Role.ADMIN.value, "unit_id": "local-unit"}

    @app.post("/api/auth/login", tags=["auth"])
    def login(payload: CredentialsInput) -> dict[str, str]:
        with local_services.session_factory() as db:
            user = db.get(User, payload.user_id)
            if user is None or not verify_pin(payload.pin, user.pin_hash):
                raise HTTPException(status_code=401, detail="invalid local credentials")
            return {"user_id": user.user_id, "role": user.role, "unit_id": user.unit_id}

    @app.post("/api/users", tags=["users"])
    def create_user(
        payload: UserCreateInput, actor_id: str = Depends(current_actor)
    ) -> dict[str, str]:
        local_services.sessions.create_user(
            actor_id=actor_id,
            user_id=payload.user_id,
            role=Role(payload.role),
            pin=payload.pin,
            unit_id=payload.unit_id,
        )
        return {"user_id": payload.user_id, "role": payload.role, "unit_id": payload.unit_id}

    @app.post("/api/scenarios/v0", tags=["scenarios"])
    def generate_v0(payload: GenerateV0Input, _: str = Depends(current_actor)) -> dict[str, Any]:
        return generate_scenario(
            payload.seed,
            ScenarioProfile(
                profile_id=payload.profile.profile_id,
                difficulty=payload.profile.difficulty,
                skill_tags=tuple(payload.profile.skill_tags),
            ),
        )

    @app.post("/api/scenarios/v1", tags=["scenarios"])
    def generate_v1(payload: GenerateV1Input, _: str = Depends(current_actor)) -> dict[str, Any]:
        return generate_scenario_v1(
            payload.seed,
            ScenarioV1Profile(
                profile_id=payload.profile.profile_id,
                difficulty=payload.profile.difficulty,
                skill_tags=tuple(payload.profile.skill_tags),
                swarm_size=payload.swarm_size,
                clutter_count=payload.clutter_count,
                terrain=payload.terrain,
                time_of_day=payload.time_of_day,
                weather=payload.weather,
            ),
        )

    @app.post("/api/sessions", tags=["sessions"])
    def create_session(
        payload: SessionCreateInput, actor_id: str = Depends(current_actor)
    ) -> dict[str, str]:
        session_id = payload.session_id or str(uuid4())
        local_services.sessions.create_training_session(
            actor_id=actor_id,
            session_id=session_id,
            trainee_id=payload.trainee_id,
            scenario=payload.scenario,
            selection_mode=payload.selection_mode,
        )
        return {"session_id": session_id}

    @app.get("/api/sessions", tags=["sessions"])
    def list_sessions(
        trainee_id: str | None = None,
        actor_id: str = Depends(current_actor),
    ) -> list[dict[str, Any]]:
        return [
            asdict(summary)
            for summary in local_services.sessions.list_sessions(
                actor_id=actor_id,
                trainee_id=trainee_id,
            )
        ]

    @app.get("/api/sessions/{session_id}", tags=["sessions"])
    def get_session(session_id: str, actor_id: str = Depends(current_actor)) -> dict[str, Any]:
        return asdict(
            local_services.sessions.get_snapshot(actor_id=actor_id, session_id=session_id)
        )

    @app.post("/api/events", tags=["sessions"])
    def ingest_event(payload: EventInput, actor_id: str = Depends(current_actor)) -> dict[str, Any]:
        return asdict(local_services.sessions.ingest_event(actor_id=actor_id, event=payload.event))

    @app.post("/api/sessions/{session_id}/complete", tags=["sessions"])
    def complete_session(session_id: str, actor_id: str = Depends(current_actor)) -> dict[str, str]:
        local_services.sessions.complete_session(actor_id=actor_id, session_id=session_id)
        return {"session_id": session_id, "status": "completed"}

    @app.post("/api/doctrines", tags=["doctrine"])
    def upload_doctrine(
        payload: DoctrineUploadInput,
        actor_id: str = Depends(current_actor),
    ) -> dict[str, Any]:
        return asdict(
            local_services.doctrines.upload(actor_id=actor_id, yaml_text=payload.yaml_text)
        )

    @app.get("/api/doctrines", tags=["doctrine"])
    def list_doctrines(actor_id: str = Depends(current_actor)) -> tuple[dict[str, str], ...]:
        return local_services.doctrines.list(actor_id=actor_id)

    @app.post("/api/sessions/{session_id}/score", tags=["scoring"])
    def score_session(
        session_id: str,
        payload: ScoreInput,
        actor_id: str = Depends(current_actor),
    ) -> dict[str, Any]:
        doctrine = local_services.doctrines.get(
            actor_id=actor_id,
            doctrine_id=payload.doctrine_id,
            version=payload.version,
        )
        report = local_services.sessions.evaluate_session(
            actor_id=actor_id,
            session_id=session_id,
            doctrine=doctrine,
        )
        snapshot = local_services.sessions.get_snapshot(actor_id=actor_id, session_id=session_id)
        updates = local_services.skills.apply_session_report_once(
            actor_id=actor_id,
            session_id=session_id,
            report=report,
            difficulty=int(snapshot.scenario["profile"]["difficulty"]),
        )
        return {"report": report.as_dict(), "skill_updates": [asdict(update) for update in updates]}

    @app.get("/api/ratings/{trainee_id}", tags=["adaptive"])
    def ratings(trainee_id: str, actor_id: str = Depends(current_actor)) -> dict[str, float]:
        return local_services.skills.ratings_for(actor_id=actor_id, trainee_id=trainee_id)

    @app.post("/api/adaptive/next", tags=["adaptive"])
    def next_scenario(
        payload: AdaptiveSelectionInput,
        actor_id: str = Depends(current_actor),
    ) -> dict[str, Any]:
        ratings = local_services.skills.ratings_for(
            actor_id=actor_id, trainee_id=payload.trainee_id
        )
        choice = select_next_scenario(
            (
                ScenarioOption(
                    profile_id=option.profile_id,
                    difficulty=option.difficulty,
                    skill_tags=tuple(option.skill_tags),
                )
                for option in payload.options
            ),
            ratings,
        )
        return asdict(choice)

    @app.get("/api/trends", tags=["adaptive"])
    def trends(actor_id: str = Depends(current_actor)) -> list[dict[str, Any]]:
        return [
            asdict(point)
            for point in unit_trends(
                session_factory=local_services.session_factory,
                actor_id=actor_id,
            )
        ]

    @app.get("/api/units/{unit_id}/summary", tags=["adaptive"])
    def unit_summary_route(unit_id: str, actor_id: str = Depends(current_actor)) -> dict[str, Any]:
        return asdict(
            unit_summary(
                session_factory=local_services.session_factory,
                actor_id=actor_id,
                unit_id=unit_id,
            )
        )

    @app.get("/api/sessions/{session_id}/replay/{t_ms}", tags=["replay"])
    def replay(
        session_id: str, t_ms: int, actor_id: str = Depends(current_actor)
    ) -> dict[str, Any]:
        snapshot = local_services.sessions.get_snapshot(actor_id=actor_id, session_id=session_id)
        return asdict(replay_frame(snapshot.scenario, t_ms))

    @app.post("/api/backups", tags=["system"])
    def backup(payload: BackupInput, actor_id: str = Depends(current_actor)) -> dict[str, str]:
        with local_services.session_factory() as db:
            require_role(db.get(User, actor_id), [Role.ADMIN])
        destination = backup_sqlite_database(
            local_services.database_path,
            local_services.database_path.parent / "backups",
            payload.name,
        )
        return {"path": str(destination)}

    if dashboard_dir is not None:
        resolved_dashboard_dir = dashboard_dir.resolve()
        if not resolved_dashboard_dir.is_dir():
            raise ValueError("dashboard_dir must be an existing built dashboard directory")
        # Mounted last, so explicit /api routes remain available to the local SPA.
        app.mount("/", StaticFiles(directory=resolved_dashboard_dir, html=True), name="dashboard")

    return app


app = create_app()
