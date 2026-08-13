"""Traduzione degli eventi tecnici in frasi italiane semplici."""

from __future__ import annotations

import re

from tamagotchi_wild.messaging import VisualizationUpdate


AREA_NAMES = {
    "food-storage": "magazzino del cibo",
    "medical-storage": "magazzino dei medicinali",
    "cage-area": "area gabbie",
    "treatment-room": "sala cure",
}
AREA_DESTINATIONS = {
    "food-storage": "nel magazzino del cibo",
    "medical-storage": "nel magazzino dei medicinali",
    "cage-area": "nell'area gabbie",
    "treatment-room": "nella sala cure",
}
AREA_ORIGINS = {
    "food-storage": "dal magazzino del cibo",
    "medical-storage": "dal magazzino dei medicinali",
    "cage-area": "dall'area gabbie",
    "treatment-room": "dalla sala cure",
}
AREA_SUBJECTS = {
    "food-storage": "Il magazzino del cibo",
    "medical-storage": "Il magazzino dei medicinali",
    "cage-area": "L'area gabbie",
    "treatment-room": "La sala cure",
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
            "initial_state": "La simulazione è iniziata.",
            "acquire_area": f"{actor} entra {_area_destination(target_id)}.",
            "release_area": f"{actor} esce {_area_origin(target_id)}.",
            "take_food": f"{actor} prende il cibo per {_task_subject(task)}.",
            "fill_bowl": f"{actor} riempie {target}.",
            "pickup_sick_animal": f"{actor} prende {target} dalla gabbia.",
            "deliver_to_treatment": f"{actor} porta {target} nella sala cure.",
            "take_medicine": (
                f"{actor} prende il medicinale per {_task_subject(task)}."
            ),
            "treat_animal": f"{actor} cura {target}.",
            "pickup_treated_animal": f"{actor} riprende {target} dopo la cura.",
            "return_animal_to_cage": f"{actor} riporta {target} nella sua gabbia.",
            "fail_task": (
                f"{actor} non riesce a completare il lavoro per "
                f"{_task_subject(task)}."
            ),
            "move_agent": f"{actor} va {_movement_destination(target_id)}.",
        }
        description = descriptions.get(
            action,
            f"{actor} esegue un'azione su {target}.",
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
    destination = "nella sala cure" if direction == "outbound" else "nella sua gabbia"
    descriptions = {
        "feeding_requested": f"{agent} chiede di riempire {subject}.",
        "outbound_transport_requested": (
            f"{agent} chiede di portare {animal} nella sala cure."
        ),
        "return_transport_requested": (
            f"{agent} chiede di riportare {animal} nella sua gabbia."
        ),
        "task_accepted": f"{agent} accetta di riempire {subject}.",
        "transport_accepted": f"{agent} accetta di portare {subject} {destination}.",
        "waiting_for_treatment_slot": (
            f"La sala cure è piena: {animal} resta nella sua gabbia."
        ),
        "task_completed": f"{agent} ha riempito {subject}.",
        "patient_ready": (
            f"{_sentence_start(animal)} è arrivato nella sala cure: "
            "il veterinario inizia la cura."
        ),
        "treatment_completed": f"{agent} ha curato {animal}.",
        "returned": f"{_sentence_start(animal)} è tornato nella sua gabbia.",
        "task_failed": f"{agent} non riesce a riempire {subject}.",
        "medical_task_failed": f"{agent} non riesce a curare {animal}.",
    }
    description = descriptions.get(event)
    return f"     ↳ {description}" if description else ""


def _claim_description(actor: str, phase: str, task: str) -> str:
    subject = _task_subject(task)
    subject_with_of = _task_subject_with_of(task)
    descriptions = {
        "feeding_coordination": f"{actor} organizza il riempimento {subject_with_of}.",
        "feeding_execution": f"{actor} si occupa {subject_with_of}.",
        "medical_coordination": f"{actor} si occupa {subject_with_of}.",
        "transport_outbound": (
            f"{actor} prepara il viaggio {subject_with_of} verso la sala cure."
        ),
        "transport_return": (
            f"{actor} prepara il ritorno {subject_with_of} nella gabbia."
        ),
    }
    return descriptions.get(phase, f"{actor} prende in carico {subject}.")


def _rejection_description(
    actor: str,
    target_id: str,
    task: str,
    requested_action: str,
    detail: str,
) -> str:
    if requested_action == "acquire_area" and "capacity" in detail:
        return (
            f"{_area_subject(target_id)} è al completo. "
            f"{actor} prova a entrare, ma deve aspettare."
        )
    if requested_action == "acquire_area" and "busy with task" in detail:
        return (
            f"{actor} prova a entrare {_area_destination(target_id)}, "
            "ma sta ancora svolgendo un'altra attività."
        )
    if "treatment room patient capacity" in detail:
        return (
            f"{actor} prova a prendere {_task_subject(task)}, ma i 3 posti "
            "della sala cure sono occupati. L'animale resta nella gabbia."
        )
    if "already carries animal" in detail:
        return (
            f"{actor} prova a prendere {_target_name(target_id)}, ma sta già "
            "trasportando un altro animale."
        )
    if "not enough food" in detail:
        return f"{actor} prova a prendere il cibo, ma le scorte sono finite."
    if "not enough medicine" in detail:
        return (
            f"{actor} prova a prendere il medicinale, ma le scorte sono finite."
        )
    if "task phase already claimed by" in detail:
        owner_id = detail.rsplit(" ", 1)[-1]
        return (
            f"{actor} prova a occuparsi {_task_subject_with_of(task)}, ma il lavoro "
            f"è già stato assegnato a {_agent_name(owner_id)}."
        )
    attempts = {
        "claim_task": "prendere in carico il lavoro",
        "take_food": "prendere il cibo",
        "fill_bowl": f"riempire {_target_name(target_id)}",
        "pickup_sick_animal": f"prendere {_target_name(target_id)}",
        "deliver_to_treatment": (
            f"portare {_target_name(target_id)} nella sala cure"
        ),
        "take_medicine": "prendere il medicinale",
        "treat_animal": f"curare {_target_name(target_id)}",
        "pickup_treated_animal": f"riprendere {_target_name(target_id)}",
        "return_animal_to_cage": f"riportare {_target_name(target_id)} in gabbia",
    }
    attempt = attempts.get(requested_action, "continuare il lavoro")
    return f"{actor} prova a {attempt}, ma in questo momento non può farlo."


def _agent_name(identifier: str) -> str:
    if identifier == "environment":
        return "Il sistema"
    labels = {
        "veterinary": "Veterinario",
        "logistics": "Operatore logistico",
        "feeding": "Addetto alimentazione",
    }
    for prefix, label in labels.items():
        number = _identifier_number(identifier, prefix)
        if number is not None:
            return f"{label} {number}"
    return identifier.replace("_", " ").strip().capitalize() or "Un operatore"


def _target_name(identifier: str) -> str:
    if identifier in AREA_NAMES:
        return AREA_NAMES[identifier]
    labels = {
        "animal": "l'animale",
        "bowl": "la ciotola",
        "cage": "la gabbia",
        "medicine_stock": "la scorta medicinali",
        "food_stock": "la scorta cibo",
    }
    for prefix, label in labels.items():
        number = _identifier_number(identifier, prefix)
        if number is not None:
            return f"{label} {number}"
    return identifier.replace("_", " ").replace("-", " ").strip() or "la destinazione"


def _task_subject(task: str) -> str:
    if number := _identifier_number(task, "feeding"):
        return f"la ciotola {number}"
    if number := _identifier_number(task, "medical"):
        return f"l'animale {number}"
    return "l'operazione"


def _task_subject_with_of(task: str) -> str:
    if number := _identifier_number(task, "feeding"):
        return f"della ciotola {number}"
    if number := _identifier_number(task, "medical"):
        return f"dell'animale {number}"
    return "dell'operazione"


def _identifier_number(identifier: str, prefix: str) -> int | None:
    match = re.fullmatch(rf"{re.escape(prefix)}[_-]?(\d+)", identifier)
    return int(match.group(1)) if match else None


def _area_destination(identifier: str) -> str:
    return AREA_DESTINATIONS.get(identifier, f"verso {_target_name(identifier)}")


def _area_origin(identifier: str) -> str:
    return AREA_ORIGINS.get(identifier, f"da {_target_name(identifier)}")


def _area_subject(identifier: str) -> str:
    return AREA_SUBJECTS.get(identifier, _sentence_start(_target_name(identifier)))


def _movement_destination(identifier: str) -> str:
    if identifier in AREA_DESTINATIONS:
        return AREA_DESTINATIONS[identifier]
    return f"verso {_target_name(identifier)}"


def _sentence_start(value: str) -> str:
    return value[:1].upper() + value[1:]


def _parse_activity(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in line.split():
        if "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result
