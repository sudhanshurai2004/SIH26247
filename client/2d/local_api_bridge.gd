class_name LocalApiBridge
extends Node
## Optional native-client sync to a locally running FastAPI service.
## Browser code never uses this address; Godot runs on the same offline desktop.

signal event_sync_finished(event_id: String, success: bool, detail: String)
signal outbox_sync_finished(success: bool, detail: String)
signal session_loaded(snapshot: Dictionary)
signal session_completion_finished(success: bool, detail: String)

@export var api_base_url := "http://127.0.0.1:8000/api"
@export var actor_id := ""
@export var pin := ""
@export var session_id := ""

var _pending_syncs := 0
var _sync_failures := 0

func load_session() -> void:
    if session_id.is_empty() or actor_id.is_empty() or pin.is_empty():
        return
    var request := HTTPRequest.new()
    add_child(request)
    var headers := ["X-Actor-Id: %s" % actor_id, "X-Pin: %s" % pin]
    var error := request.request("%s/sessions/%s" % [api_base_url, session_id], headers)
    if error != OK:
        request.queue_free()
        return
    var result: Array = await request.request_completed
    request.queue_free()
    if int(result[1]) < 200 or int(result[1]) >= 300:
        return
    var parsed = JSON.parse_string(result[3].get_string_from_utf8())
    if parsed is Dictionary:
        session_loaded.emit(parsed)

func sync_outbox(events: Array[Dictionary]) -> void:
    """Retry a durable outbox. Exact repeated payloads are server-idempotent."""
    if events.is_empty():
        outbox_sync_finished.emit(true, "No pending local events")
        return
    _sync_failures = 0
    for event in events:
        sync_event(event)
    _emit_outbox_result_if_ready()

func complete_session() -> void:
    """Complete only after all emitted event requests have settled successfully."""
    if session_id.is_empty() or actor_id.is_empty() or pin.is_empty():
        session_completion_finished.emit(false, "Local session credentials are not configured")
        return
    while _pending_syncs > 0:
        await get_tree().process_frame
    if _sync_failures > 0:
        session_completion_finished.emit(false, "Event sync failed; local outbox remains available for retry")
        return
    var request := HTTPRequest.new()
    add_child(request)
    var headers := [
        "Content-Type: application/json",
        "X-Actor-Id: %s" % actor_id,
        "X-Pin: %s" % pin,
    ]
    var error := request.request(
        "%s/sessions/%s/complete" % [api_base_url, session_id],
        headers,
        HTTPClient.METHOD_POST,
        "{}"
    )
    if error != OK:
        request.queue_free()
        session_completion_finished.emit(false, "Could not contact local API")
        return
    var result: Array = await request.request_completed
    request.queue_free()
    var success := int(result[1]) >= 200 and int(result[1]) < 300
    session_completion_finished.emit(success, result[3].get_string_from_utf8())

func sync_event(event: Dictionary) -> void:
    if event.is_empty():
        return
    if actor_id.is_empty() or pin.is_empty():
        _sync_failures += 1
        event_sync_finished.emit(
            str(event.get("event_id", "")), false, "Local credentials are not configured"
        )
        return
    _pending_syncs += 1
    var request := HTTPRequest.new()
    add_child(request)
    var headers := [
        "Content-Type: application/json",
        "X-Actor-Id: %s" % actor_id,
        "X-Pin: %s" % pin,
    ]
    var error := request.request(
        "%s/events" % api_base_url,
        headers,
        HTTPClient.METHOD_POST,
        JSON.stringify({"event": event})
    )
    if error != OK:
        request.queue_free()
        _pending_syncs -= 1
        _sync_failures += 1
        event_sync_finished.emit(str(event.get("event_id", "")), false, "Could not contact local API")
        _emit_outbox_result_if_ready()
        return
    var result: Array = await request.request_completed
    request.queue_free()
    _pending_syncs -= 1
    var response_code: int = result[1]
    var response_body: String = result[3].get_string_from_utf8()
    var success := response_code >= 200 and response_code < 300
    if not success:
        _sync_failures += 1
    event_sync_finished.emit(str(event.get("event_id", "")), success, response_body)
    _emit_outbox_result_if_ready()

func _emit_outbox_result_if_ready() -> void:
    if _pending_syncs == 0:
        outbox_sync_finished.emit(
            _sync_failures == 0,
            "Outbox synchronized" if _sync_failures == 0 else "One or more outbox events failed"
        )
