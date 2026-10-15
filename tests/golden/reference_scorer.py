"""Reference scorer for the golden cases. Pure Python, no I/O besides YAML load.
The real core/scoring module must reproduce these numbers within 0.01."""
import yaml


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)          # safe loader only

def validate_doctrine(d):
    errs = []
    w = d.get("weights", {})
    if abs(sum(w.values()) - 1.0) > 1e-9:
        errs.append("weights_sum_invalid")
    for cls in d.get("response_matrix", {}):
        if cls not in d.get("classes", []):
            errs.append("unknown_class:" + cls)
    return errs

def score(d, targets, events, status="completed"):
    seen, evs, dups = set(), [], 0
    for e in events:                       # idempotent ingestion by event id
        if e["id"] in seen:
            dups += 1
            continue
        seen.add(e["id"]); evs.append(e)
    w, per, crit, cap = d["weights"], {}, [], False
    for t in targets:
        te = sorted([e for e in evs if e["target"] == t["id"]], key=lambda e: e["t_ms"])
        det = next((e for e in te if e["type"] == "DETECT"), None)
        cls = next((e for e in te if e["type"] == "CLASSIFY" and det and e["t_ms"] >= det["t_ms"]), None)
        res = next((e for e in te if e["type"] == "RESPOND"), None)
        dd = 1.0 if det else 0.0
        dt = max(0.0, (det["t_ms"] - t["t_visible_ms"]) / 1000) if det else None
        tc = max(0.0, 1 - dt / d["dt_max_s"]) if det else 0.0
        cc = 0.0
        if cls:
            if cls["value"] == t["true_class"]: cc = 1.0
            elif cls["value"] in d["partial_credit"].get(t["true_class"], []): cc = 0.5
        rc = 0.0
        if det and res and t["true_class"] in d["response_matrix"]:
            m = d["response_matrix"][t["true_class"]][t["response_zone"]]
            rc = 1.0 if res["value"] in m["best"] else 0.5 if res["value"] in m["acceptable"] else 0.0
        s = w["detect"]*dd + w["classify"]*cc + w["respond"]*rc + w["time"]*tc
        per[t["id"]] = round(s, 4)
        if res and res["value"] in d["engagement_actions"] and t["true_class"] != "hostile_small_uas":
            crit.append("engage_nonhostile:" + t["id"])
            if t["true_class"] == "friendly_aircraft": cap = True
        if status == "completed" and t["true_class"] == "hostile_small_uas" and t.get("reaches_inner") and not res:
            crit.append("miss_hostile_at_inner_zone:" + t["id"])
    raw = 100 * sum(per.values()) / len(targets)
    total = max(0.0, raw - d["critical_penalty_points"] * len(crit))
    if cap: total = min(total, d["cap_on_engage_friendly"])
    return {"per_target": per, "critical": crit, "total": round(total, 2),
            "ignored_duplicates": dups, "rating_eligible": status == "completed"}
