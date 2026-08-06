"""Record-shape and commitment correlation checks for semantic audit."""

from police_agent.peer.step_zero import turn_records


def turns(records, label, failures):
    output = []
    previous = 0
    for record in turn_records(records):
        payload = record.get("payload") if isinstance(record, dict) else None
        if not isinstance(payload, dict) or not isinstance(payload.get("step"), int):
            failures.append(f"{label} record is missing an integer step")
            continue
        step = payload["step"]
        if step != previous + 1:
            failures.append(f"{label} steps are not contiguous at {step}")
        previous = step
        output.append((step, payload, record))
    return output


def messages(source, failures):
    output = []
    previous = 0
    for message in source or []:
        if not isinstance(message, dict) or not isinstance(message.get("step"), int):
            failures.append("received message is missing an integer step")
            continue
        step = message["step"]
        if step != previous + 1:
            failures.append(f"received steps are not contiguous at {step}")
        previous = step
        output.append((step, message))
    return output


def match_messages(remote, received, failures):
    if len(remote) != len(received):
        failures.append("revealed record count does not match received turns")
    for record, message in zip(remote, received, strict=False):
        if record[0] != message[0]:
            failures.append(f"revealed step {record[0]} does not match message step {message[0]}")
        if record[2].get("commit") != message[1].get("commit"):
            failures.append(f"turn {record[0]} commitment does not match the received message")


def split_trailing_claim(remote, received_messages):
    """A capture confirmation can arrive as an extra, unrecorded terminal
    message: the peer that sends it never opens a new sealed step for it, so
    it reuses the last remote step's number and has no counterpart in
    `remote`. Pull a message shaped like one out of the *raw* list, before
    `messages()` ever sees it -- its own step-contiguity check would read the
    reused step as a duplicate, and the per-turn correspondence check that
    follows expects `remote` and `received` to pair up 1:1. Any other length
    or shape is still a real failure.
    """
    source = list(received_messages or [])
    if remote and len(source) == len(remote) + 1:
        message = source[-1]
        step = message.get("step") if isinstance(message, dict) else None
        response = message.get("claim_response") if isinstance(message, dict) else None
        if step == remote[-1][0] and isinstance(response, dict) and response.get("caught") is True:
            return source[:-1], (step, message)
    return source, None


def check_local_coverage(local, log_by_step, failures):
    if len(local) != len(log_by_step):
        failures.append("local sealed record count does not match the move log")


def cell(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(isinstance(item, int) for item in value):
        return None
    return tuple(value)


def result(failures, corrections, terminal):
    return {
        "semantic_passed": not failures,
        "semantic_failures": failures,
        "semantic_corrections": corrections,
        "terminal": terminal,
    }
