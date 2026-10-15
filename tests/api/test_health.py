"""Smoke test for the local API shell used by the one-command dev workflow."""

from pathlib import Path

from fastapi.testclient import TestClient

from core.api.app import app, create_app
from core.api.runtime import create_local_services


def test_health_endpoint_reports_local_service_status() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "stage": "8", "offline_only": True}


def test_built_dashboard_can_share_the_local_api_origin(tmp_path: Path) -> None:
    dashboard = tmp_path / "dashboard"
    dashboard.mkdir()
    (dashboard / "index.html").write_text("<h1>local dashboard</h1>", encoding="utf-8")
    client = TestClient(
        create_app(
            create_local_services(tmp_path / "trainer.sqlite3"),
            dashboard_dir=dashboard,
        )
    )

    assert client.get("/").text == "<h1>local dashboard</h1>"
    assert client.get("/api/health").status_code == 200
