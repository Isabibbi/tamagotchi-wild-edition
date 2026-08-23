"""Translation of technical events into simple English phrases."""

from __future__ import annotations

import re

from tamagotchi_wild.messaging import VisualizationUpdate


AREA_NAMES = {
    "food-storage": "food storage",
    "medical-storage": "medical storage",
    "cage-area": "cage area",
    "treatment-room": "treatment room",
}
AREA_DESTINATIONS = {
    "food-storage": "into the food storage",
    "medical-storage": "into the medical storage",
    "cage-area": "into the cage area",
    "treatment-room": "into the treatment room",
}
AREA_ORIGINS = {
    "food-storage": "from the food storage",
    "medical-storage": "from the medical storage",
    "cage-area": "from the cage area",
    "treatment-room": "from the treatment room",
}
AREA_SUBJECTS = {
    "food-storage": "The food storage",
    "medical-storage": "The medical storage",
    "cage-area": "The cage area",
    "treatment-room": "The treatment room",
}


def timeline_entries(
    update: VisualizationUpdate,
    seen_activity_count: int,
) -> tuple[tuple[str, ...], int]:
    new_activity = update.activity_lines[seen_activity_count:]
    entries = [describe_activity(line) for line in new_activity]
    entries.append(describe_environment_event(update.event))
    return tuple(entry for entry in entries if entry), len(update.activity_lines)


def describe_environment_event(event: dict) -> str:
    sequence = event.get("sequence", 0)
    action = event.get("action", "unknown")
    actor = _agent_name(str(event.get("actor_id", "unknown")))
    target_id = str(event.get("target_id", "unknown"))
    target = _target_name(target_id)
    task = str(event.get("task_id", ""))
    detail = str(event.get("detail", ""))
    requested_action = str(event.get("requested_action", ""))
    prefix = f"#{sequence:03d}" if isinstance(sequence, int) else "#---"

    if action == "claim_task":
        description = _claim_description(actor, target_id, task)
    elif action == "action_rejected":
        description = _rejection_description(
            actor,
            target_id,
            task,
            requested_action,
            detail,
        )
    else:
        descriptions = {
            "initial_state": "Simulation started.",
            "acquire_area": f"{actor} enters {_area_destination(target_id)}.",
            "release_area": f"{actor} leaves {_area_origin(target_id)}.",
            "take_food": f"{actor} picks up food for {_task_subject(task)}.",
            "fill_bowl": f"{actor} fills {target}.",
            "pickup_sick_animal": f"{actor} picks up {target} from the cage.",
            "deliver_to_treatment": f"{actor} brings {target} to the treatment room.",
            "take_medicine": (
                f"{actor} picks up medicine for {_task_subject(task)}."
            ),
            "treat_animal": f"{actor} treats {target}.",
            "pickup_treated_animal": f"{actor} collects {target} after treatment.",
            "return_animal_to_cage": f"{actor} returns {target} to its cage.",
            "fail_task": (
                f"{actor} could not complete the task for "
                f"{_task_subject(task)}."
            ),
            "move_agent": f"{actor} moves {_movement_destination(target_id)}.",
        }
        description = descriptions.get(
            action,
            f"{actor} performs an action on {target}.",
        )
    return f"{prefix} · {description}"


def describe_activity(line: str) -> str:
    values = _parse_activity(line)
    event = values.get("event", "")
    task = values.get("task", "")
    agent = _agent_name(values.get("agent", ""))
    subject = _task_subject(task)
    animal = (
        _target_name(values.get("animal", ""))
        if values.get("animal")
        else subject
    )
    direction = values.get("direction", "")
    destination = "into the treatment room" if direction == "outbound" else "to its cage"
    descriptions = {
        "feeding_requested": f"{agent} requests refill of {subject}.",
        "outbound_transport_requested": (
            f"{agent} requests transport of {animal} to the treatment room."
        ),
        "return_transport_requested": (
            f"{agent} requests return of {animal} to its cage."
        ),
        "task_accepted": f"{agent} accepts the refill of {subject}.",
        "feeding_task_waiting": (
            f"{agent} is already filling another bowl: "
            f"the request for {subject} is on hold."
        ),
        "transport_accepted": f"{agent} accepts transport of {subject} {destination}.",
        "waiting_for_treatment_slot": (
            f"Treatment room is full: {animal} stays in its cage."
        ),
        "task_completed": f"{agent} has filled {subject}.",
        "patient_ready": (
            f"{_sentence_start(animal)} has arrived in the treatment room: "
            "the vet begins treatment."
        ),
        "treatment_completed": f"{agent} has treated {animal}.",
        "returned": f"{_sentence_start(animal)} has returned to its cage.",
        "task_failed": f"{agent} could not fill {subject}.",
        "medical_task_failed": f"{agent} could not treat {animal}.",
    }
    description = descriptions.get(event)
    return f"     ↳ {description}" if description else ""


def _claim_description(actor: str, phase: str, task: str) -> str:
    subject = _task_subject(task)
    subject_with_of = _task_subject_with_of(task)
    descriptions = {
        "feeding_coordination": f"{actor} coordinates the refill of {subject_with_of}.",
        "feeding_execution": f"{actor} takes care of {subject_with_of}.",
        "medical_coordination": f"{actor} takes care of {subject_with_of}.",
        "transport_outbound": (
            f"{actor} prepares the trip for {subject_with_of} to the treatment room."
        ),
        "transport_return": (
            f"{actor} prepares the return of {subject_with_of} to the cage."
        ),
    }
    return descriptions.get(phase, f"{actor} takes on the task for {subject}.")


def _rejection_description(
    actor: str,
    target_id: str,
    task: str,
    requested_action: str,
    detail: str,
) -> str:
    if requested_action == "acquire_area" and "capacity" in detail:
        return (
            f"{_area_subject(target_id)} is at full capacity. "
            f"{actor} tries to enter but must wait."
        )
    if requested_action == "acquire_area" and "busy with task" in detail:
        return (
            f"{actor} tries to enter {_area_destination(target_id)}, "
            "but is still busy with another task."
        )
    if "treatment room patient capacity" in detail:
        return (
            f"{actor} tries to pick up {_task_subject(task)}, but all 3 slots "
            "in the treatment room are taken. The animal stays in the cage."
        )
    if "already carries animal" in detail:
        return (
            f"{actor} tries to pick up {_target_name(target_id)}, but is already "
            "carrying another animal."
        )
    if "not enough food" in detail:
        return f"{actor} tries to pick up food, but the stock is empty."
    if "not enough medicine" in detail:
        return (
            f"{actor} tries to pick up medicine, but the stock is empty."
        )
    if "task phase already claimed by" in detail:
        owner_id = detail.rsplit(" ", 1)[-1]
        return (
            f"{actor} tries to handle {_task_subject_with_of(task)}, but the task "
            f"is already assigned to {_agent_name(owner_id)}."
        )
    attempts = {
        "claim_task": "take on the task",
        "take_food": "pick up food",
        "fill_bowl": f"fill {_target_name(target_id)}",
        "pickup_sick_animal": f"pick up {_target_name(target_id)}",
        "deliver_to_treatment": (
            f"bring {_target_name(target_id)} to the treatment room"
        ),
        "take_medicine": "pick up medicine",
        "treat_animal": f"treat {_target_name(target_id)}",
        "pickup_treated_animal": f"collect {_target_name(target_id)}",
        "return_animal_to_cage": f"return {_target_name(target_id)} to cage",
    }
    attempt = attempts.get(requested_action, "continue the task")
    return f"{actor} tries to {attempt}, but cannot do so right now."


def _agent_name(identifier: str) -> str:
    if identifier == "environment":
        return "The system"
    labels = {
        "veterinary": "Vet",
        "logistics": "Logistics operator",
        "feeding": "Feeding staff",
    }
    for prefix, label in labels.items():
        number = _identifier_number(identifier, prefix)
        if number is not None:
            return f"{label} {number}"
    return identifier.replace("_", " ").strip().capitalize() or "An operator"


def _target_name(identifier: str) -> str:
    if identifier in AREA_NAMES:
        return AREA_NAMES[identifier]
    labels = {
        "animal": "the animal",
        "bowl": "the bowl",
        "cage": "the cage",
        "medicine_stock": "the medicine stock",
        "food_stock": "the food stock",
    }
    for prefix, label in labels.items():
        number = _identifier_number(identifier, prefix)
        if number is not None:
            return f"{label} {number}"
    return identifier.replace("_", " ").replace("-", " ").strip() or "the destination"


def _task_subject(task: str) -> str:
    if number := _identifier_number(task, "feeding"):
        return f"bowl {number}"
    if number := _identifier_number(task, "medical"):
        return f"animal {number}"
    return "the operation"


def _task_subject_with_of(task: str) -> str:
    if number := _identifier_number(task, "feeding"):
        return f"bowl {number}"
    if number := _identifier_number(task, "medical"):
        return f"animal {number}"
    return "the operation"


def _identifier_number(identifier: str, prefix: str) -> int | None:
    match = re.fullmatch(rf"{re.escape(prefix)}[_-]?(\d+)", identifier)
    return int(match.group(1)) if match else None


def _area_destination(identifier: str) -> str:
    return AREA_DESTINATIONS.get(identifier, f"towards {_target_name(identifier)}")


def _area_origin(identifier: str) -> str:
    return AREA_ORIGINS.get(identifier, f"from {_target_name(identifier)}")


def _area_subject(identifier: str) -> str:
    return AREA_SUBJECTS.get(identifier, _sentence_start(_target_name(identifier)))


def _movement_destination(identifier: str) -> str:
    if identifier in AREA_DESTINATIONS:
        return AREA_DESTINATIONS[identifier]
    return f"towards {_target_name(identifier)}"


def _sentence_start(value: str) -> str:
    return value[:1].upper() + value[1:]


def _parse_activity(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in line.split():
        if "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result
