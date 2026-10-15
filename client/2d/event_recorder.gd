extends Node
## Writes contract-shaped trainee events to a local NDJSON outbox for idempotent sync.

signal event_recorded(event: Dictionary)

var session_id := ""
var scenario_id := ""
var trainee_id := ""
var sequence := 0
var outbox_path := ""

func configure(next_session_id: String, next_scenario_id: String, next_trainee_id: String) -> void:
    session_id = next_session_id
    scenario_id = next_scenario_id
    trainee_id = next_trainee_id
    sequence = 0
    outbox_path = "user://event-outbox/%s.ndjson" % session_id
    DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("user://event-outbox"))
    for event in outbox_events():
        sequence = max(sequence, int(event.get("sequence", -1)) + 1)

func outbox_events() -> Array[Dictionary]:
    """Read locally durable events so API retries preserve idempotency keys."""
    var events: Array[Dictionary] = []
    if outbox_path.is_empty() or not FileAccess.file_exists(outbox_path):
        return events
    var file := FileAccess.open(outbox_path, FileAccess.READ)
    if file == null:
        return events
    while not file.eof_reached():
        var line := file.get_line().strip_edges()
        if line.is_empty():
            continue
        var parsed = JSON.parse_string(line)
        if parsed is Dictionary:
            events.append(parsed)
    file.close()
    return events

func record_detect(target_id: String, playback_ms: int) -> Dictionary:
    return _record("detect", playback_ms, {"target_id": target_id})

func record_classify(target_id: String, classification: String, playback_ms: int) -> Dictionary:
    return _record("classify", playback_ms, {"target_id": target_id, "classification": classification})

func record_assess(target_id: String, assessment: String, playback_ms: int) -> Dictionary:
    return _record("assess", playback_ms, {"target_id": target_id, "assessment": assessment})

func record_respond(target_id: String, response: String, playback_ms: int) -> Dictionary:
    # Allowed values stay abstract: monitor, report, escalate, defer.
    return _record("respond", playback_ms, {"target_id": target_id, "response": response})

func record_interruption(reason: String, playback_ms: int) -> Dictionary:
    return _record("session_interrupted", playback_ms, {"reason": reason})

func _record(event_type: String, playback_ms: int, payload: Dictionary) -> Dictionary:
    if session_id.is_empty() or scenario_id.is_empty() or trainee_id.is_empty():
        push_error("EventRecorder must be configured before recording events.")
        return {}
    var event := {
        "contract_version": "1.0",
        "event_id": _deterministic_uuid(event_type, playback_ms),
        "session_id": session_id,
        "scenario_id": scenario_id,
        "trainee_id": trainee_id,
        "event_type": event_type,
        "t_offset_ms": playback_ms,
        "sequence": sequence,
        "payload": payload,
    }
    sequence += 1
    var access_mode := FileAccess.READ_WRITE if FileAccess.file_exists(outbox_path) else FileAccess.WRITE_READ
    var file := FileAccess.open(outbox_path, access_mode)
    if file == null:
        push_error("Could not open local event outbox.")
        return {}
    file.seek_end()
    file.store_line(JSON.stringify(event))
    file.close()
    event_recorded.emit(event)
    return event

func _deterministic_uuid(event_type: String, playback_ms: int) -> String:
    # A retry emits the same id for a session/sequence/action and is therefore idempotent.
    var digest := ("%s|%s|%s|%s" % [session_id, sequence, event_type, playback_ms]).sha256_text()
    return "%s-%s-4%s-8%s-%s" % [
        digest.substr(0, 8),
        digest.substr(8, 4),
        digest.substr(13, 3),
        digest.substr(17, 3),
        digest.substr(20, 12),
    ]
