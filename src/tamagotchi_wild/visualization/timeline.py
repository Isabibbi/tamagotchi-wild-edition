"""Traduzione degli eventi tecnici in una cronologia leggibile."""

from __future__ import annotations

from tamagotchi_wild.messaging import VisualizationUpdate


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
    actor = event.get("actor_id", "unknown")
    target = event.get("target_id", "unknown")
    task = event.get("task_id", "")
    detail = event.get("detail", "")
    requested_action = event.get("requested_action", "")
    prefix = f"#{sequence:03d}" if isinstance(sequence, int) else "#---"
    rejection_description = (
        f"{actor} attende un posto in {target} per il task {task}"
        if requested_action == "acquire_area" and "capacity" in detail
        else (
            f"richiesta '{requested_action}' di {actor} rifiutata su {target} "
            f"({detail})"
        )
    )
    descriptions = {
        "initial_state": "Environment pubblica lo stato iniziale alla GUI SPADE",
        "claim_task": f"{actor} ottiene la fase '{target}' del task {task}",
        "acquire_area": f"{actor} entra in {target} per il task {task}",
        "release_area": f"{actor} libera {target} dopo il task {task}",
        "take_food": f"{actor} preleva una razione di cibo per {task}",
        "fill_bowl": f"{actor} riempie {target} per {task}",
        "pickup_sick_animal": f"{actor} preleva {target} dalla gabbia",
        "deliver_to_treatment": f"{actor} consegna {target} in Treatment Room",
        "take_medicine": f"{actor} preleva una dose di medicinale per {task}",
        "treat_animal": f"{actor} cura {target}",
        "pickup_treated_animal": f"{actor} preleva {target} dopo la cura",
        "return_animal_to_cage": f"{actor} riporta {target} nella sua gabbia",
        "fail_task": f"{actor} conclude {task} con un rifiuto",
        "move_agent": f"{actor} si sposta verso {target}",
        "action_rejected": rejection_description,
    }
    fallback = f"{actor}: {action} su {target}"
    return f"{prefix} · {descriptions.get(action, fallback)}"


def describe_activity(line: str) -> str:
    values = _parse_activity(line)
    event = values.get("event", "")
    task = values.get("task", "")
    agent = values.get("agent", "")
    descriptions = {
        "feeding_requested": f"{agent} rileva la ciotola vuota e richiede Feeding ({task})",
        "outbound_transport_requested": f"{agent} richiede il trasporto verso Treatment Room ({task})",
        "return_transport_requested": f"{agent} richiede il ritorno dell'animale in gabbia ({task})",
        "task_accepted": f"{agent} accetta il task di alimentazione {task}",
        "transport_accepted": f"{agent} accetta il trasporto {values.get('direction', '')} ({task})",
        "waiting_for_treatment_slot": (
            f"{agent} lascia il paziente in gabbia: i 3 posti della Treatment Room sono occupati ({task})"
        ),
        "task_completed": f"{agent} completa il task di alimentazione {task}",
        "patient_ready": f"{agent} segnala che il paziente è pronto ({task})",
        "treatment_completed": f"{agent} completa il trattamento ({task})",
        "returned": f"{agent} conferma il ritorno in gabbia ({task})",
        "task_failed": f"{agent} non completa il task {task}",
        "medical_task_failed": f"{agent} non completa la cura {task}",
    }
    description = descriptions.get(event)
    return f"     ↳ {description}" if description else ""


def _parse_activity(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in line.split():
        if "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result
