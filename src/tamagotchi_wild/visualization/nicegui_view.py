"""Proiezioni HTML/SVG pure usate dalla dashboard NiceGUI."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape


CELL_SIZE = 64
GRID_WIDTH = 14 * CELL_SIZE
GRID_HEIGHT = 10 * CELL_SIZE

AREA_COLORS = {
    "corridor": "#e2e8f0",
    "food_storage": "#fef3c7",
    "medical_storage": "#dbeafe",
    "cage_area": "#dcfce7",
    "treatment_room": "#ffe4e6",
}
AREA_LABELS = {
    "corridor": "CORRIDOR",
    "food_storage": "FOOD STORAGE",
    "medical_storage": "MEDICAL STORAGE",
    "cage_area": "CAGE AREA",
    "treatment_room": "TREATMENT ROOM",
}
ROLE_COLORS = {
    "veterinary": "#2563eb",
    "logistics": "#7c3aed",
    "feeding": "#ea580c",
}
ROLE_LABELS = {
    "veterinary": "Veterinary",
    "logistics": "Logistics",
    "feeding": "Feeding",
}
ROLE_INITIALS = {"veterinary": "V", "logistics": "L", "feeding": "F"}
PATH_COLORS = (
    "#e11d48",
    "#2563eb",
    "#16a34a",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#ca8a04",
)
HEALTH_COLORS = {
    "sick": "#dc2626",
    "in_outbound_transport": "#9333ea",
    "in_treatment": "#f59e0b",
    "treated": "#0ea5e9",
    "in_return_transport": "#9333ea",
    "healthy": "#16a34a",
}
HEALTH_LABELS = {
    "sick": "Malato",
    "in_outbound_transport": "Verso le cure",
    "in_treatment": "In trattamento",
    "treated": "Trattato",
    "in_return_transport": "Rientro in gabbia",
    "healthy": "Sano",
}
SPECIES_EMOJI = {
    "fox": "🦊",
    "owl": "🦉",
    "hedgehog": "🦔",
    "badger": "🦡",
    "hare": "🐇",
    "deer": "🦌",
    "squirrel": "🐿️",
    "tortoise": "🐢",
    "heron": "🐦",
    "bat": "🦇",
}


@dataclass(frozen=True, slots=True)
class DashboardMetrics:
    healthy_animals: int
    animal_count: int
    filled_bowls: int
    bowl_count: int
    completed_medical_tasks: int
    medical_task_count: int
    food_remaining: int
    medicine_remaining: int
    active_operators: int


def snapshot_metrics(snapshot: dict) -> DashboardMetrics:
    medical_tasks = [
        task for task in snapshot["tasks"] if task["kind"] == "treat_animal"
    ]
    return DashboardMetrics(
        healthy_animals=sum(
            animal["health"] == "healthy" for animal in snapshot["animals"]
        ),
        animal_count=len(snapshot["animals"]),
        filled_bowls=sum(
            bowl["level"] == bowl["capacity"] for bowl in snapshot["bowls"]
        ),
        bowl_count=len(snapshot["bowls"]),
        completed_medical_tasks=sum(
            task["status"] == "completed" for task in medical_tasks
        ),
        medical_task_count=len(medical_tasks),
        food_remaining=(snapshot["food"][0]["quantity"] if snapshot["food"] else 0),
        medicine_remaining=(
            snapshot["medicine"][0]["quantity"] if snapshot["medicine"] else 0
        ),
        active_operators=len(snapshot.get("navigation", ())),
    )


def render_grid_svg(snapshot: dict) -> str:
    """Disegna operatori, target e percorsi A* senza modificare lo stato."""

    area_by_cell = {
        (cell["x"], cell["y"]): area["kind"]
        for area in snapshot["areas"]
        for cell in area["cells"]
    }
    active_ids = {
        agent_id
        for access in snapshot["area_access"]
        for agent_id in access["occupants"]
    }
    navigation_by_agent = {
        item["agent_id"]: item for item in snapshot.get("navigation", ())
    }
    path_colors = _agent_path_colors(snapshot)
    agents_by_id = {agent["id"]: agent for agent in snapshot["agents"]}
    chunks = [
        f'<svg viewBox="0 0 {GRID_WIDTH} {GRID_HEIGHT}" '
        'role="img" aria-label="Griglia del centro di recupero" '
        'xmlns="http://www.w3.org/2000/svg">',
        '<rect width="100%" height="100%" rx="18" fill="#f8fafc"/>',
    ]

    for y in range(snapshot["height"]):
        for x in range(snapshot["width"]):
            kind = area_by_cell[(x, y)]
            chunks.append(
                f'<rect x="{x * CELL_SIZE}" y="{y * CELL_SIZE}" '
                f'width="{CELL_SIZE}" height="{CELL_SIZE}" '
                f'fill="{AREA_COLORS[kind]}" stroke="#cbd5e1" stroke-width="1"/>'
            )

    for area in snapshot["areas"]:
        first = min(area["cells"], key=lambda cell: (cell["y"], cell["x"]))
        chunks.append(
            f'<text x="{first["x"] * CELL_SIZE + 8}" '
            f'y="{first["y"] * CELL_SIZE + 15}" '
            'font-family="Inter,Segoe UI,sans-serif" font-size="9" '
            'font-weight="800" fill="#334155" letter-spacing="0.8">'
            f'{AREA_LABELS[area["kind"]]}</text>'
        )

    for agent in snapshot["agents"]:
        navigation = navigation_by_agent.get(agent["id"])
        if navigation is None:
            continue
        color = path_colors[agent["id"]]
        target = navigation["target"]
        path = navigation["path"]
        points = [agent["position"], *path]
        if len(points) > 1:
            point_text = " ".join(
                f'{item["x"] * CELL_SIZE + CELL_SIZE / 2},'
                f'{item["y"] * CELL_SIZE + CELL_SIZE / 2}'
                for item in points
            )
            chunks.append(
                f'<polyline points="{point_text}" fill="none" stroke="{color}" '
                'stroke-width="4" stroke-linecap="round" stroke-linejoin="round" '
                'stroke-dasharray="7 5" opacity="0.88"/>'
            )
        target_x = target["x"] * CELL_SIZE
        target_y = target["y"] * CELL_SIZE
        chunks.append(
            f'<g><title>{escape(agent["id"])} target '
            f'({target["x"]}, {target["y"]})</title>'
            f'<rect x="{target_x + 5}" y="{target_y + 5}" '
            f'width="{CELL_SIZE - 10}" height="{CELL_SIZE - 10}" rx="9" '
            f'fill="{color}" fill-opacity="0.10" stroke="{color}" '
            'stroke-width="3" stroke-dasharray="6 4"/>'
            f'<circle cx="{target_x + CELL_SIZE / 2}" '
            f'cy="{target_y + CELL_SIZE / 2}" r="5" fill="{color}"/></g>'
        )

    for cage in snapshot["cages"]:
        x = cage["position"]["x"] * CELL_SIZE
        y = cage["position"]["y"] * CELL_SIZE
        cage_id = escape(cage["id"])
        chunks.extend(
            (
                f'<g><title>{cage_id}</title>',
                f'<rect x="{x + 7}" y="{y + 19}" width="{CELL_SIZE - 14}" '
                f'height="{CELL_SIZE - 25}" rx="7" fill="none" '
                'stroke="#64748b" stroke-width="2" stroke-dasharray="4 3"/>',
                f'<text x="{x + 10}" y="{y + 29}" font-family="Inter,Segoe UI,sans-serif" '
                f'font-size="7" font-weight="700" fill="#64748b">{cage_id}</text></g>',
            )
        )

    for bowl in snapshot["bowls"]:
        x = bowl["position"]["x"] * CELL_SIZE
        y = bowl["position"]["y"] * CELL_SIZE
        full = bowl["level"] == bowl["capacity"]
        color = "#22c55e" if full else "#ef4444"
        state = "piena" if full else "vuota"
        chunks.append(
            f'<g><title>{escape(bowl["id"])}: {state}</title>'
            f'<ellipse cx="{x + 51}" cy="{y + 51}" rx="8" ry="5" '
            f'fill="{color}" stroke="#ffffff" stroke-width="2"/></g>'
        )

    animals_per_cell: dict[tuple[int, int], int] = {}
    for animal in snapshot["animals"]:
        position = animal["position"]
        if animal["carried_by"] in agents_by_id:
            position = agents_by_id[animal["carried_by"]]["position"]
        cell = (position["x"], position["y"])
        local_index = animals_per_cell.get(cell, 0)
        animals_per_cell[cell] = local_index + 1
        x = position["x"] * CELL_SIZE + 31 + (local_index % 2) * 12
        y = position["y"] * CELL_SIZE + 43
        color = HEALTH_COLORS.get(animal["health"], "#64748b")
        emoji = SPECIES_EMOJI.get(animal["species"], "🐾")
        title = escape(
            f'{animal["id"]} · {animal["species"]} · '
            f'{HEALTH_LABELS.get(animal["health"], animal["health"])} · '
            f'{animal["condition"]}'
        )
        chunks.extend(
            (
                f'<g><title>{title}</title>',
                f'<circle cx="{x}" cy="{y}" r="13" fill="#ffffff" '
                f'stroke="{color}" stroke-width="4"/>',
                f'<text x="{x}" y="{y + 6}" text-anchor="middle" '
                f'font-size="18">{emoji}</text></g>',
            )
        )

    agents_per_cell: dict[tuple[int, int], int] = {}
    for agent in snapshot["agents"]:
        position = agent["position"]
        cell = (position["x"], position["y"])
        local_index = agents_per_cell.get(cell, 0)
        agents_per_cell[cell] = local_index + 1
        x = position["x"] * CELL_SIZE + 15 + local_index * 23
        y = position["y"] * CELL_SIZE + 18
        color = ROLE_COLORS[agent["role"]]
        path_color = path_colors[agent["id"]]
        navigation = navigation_by_agent.get(agent["id"])
        state = (
            f'target ({navigation["target"]["x"]}, {navigation["target"]["y"]})'
            if navigation
            else "senza target"
        )
        access_state = "accesso attivo" if agent["id"] in active_ids else "in transito"
        title = escape(
            f'{agent["id"]} · {ROLE_LABELS[agent["role"]]} · {access_state} · {state}'
        )
        chunks.extend(
            (
                f'<g><title>{title}</title>',
                f'<circle cx="{x}" cy="{y}" r="13" fill="#ffffff" '
                f'stroke="{path_color}" stroke-width="4"/>',
                f'<circle cx="{x}" cy="{y}" r="10" fill="{color}" '
                f'stroke="{"#facc15" if agent["id"] in active_ids else "#ffffff"}" '
                'stroke-width="2"/>',
                f'<text x="{x}" y="{y + 4}" text-anchor="middle" '
                'font-family="Inter,Segoe UI,sans-serif" font-size="10" '
                f'font-weight="800" fill="#ffffff">{ROLE_INITIALS[agent["role"]]}</text></g>',
            )
        )

    chunks.append("</svg>")
    return "".join(chunks)


def render_operator_roster(snapshot: dict) -> str:
    area_for_agent = {
        agent_id: access["area_id"]
        for access in snapshot["area_access"]
        for agent_id in access["occupants"]
    }
    navigation_by_agent = {
        item["agent_id"]: item for item in snapshot.get("navigation", ())
    }
    path_colors = _agent_path_colors(snapshot)
    cards = []
    for agent in snapshot["agents"]:
        area = area_for_agent.get(agent["id"])
        navigation = navigation_by_agent.get(agent["id"])
        active = area is not None or navigation is not None
        if navigation is not None and navigation["status"] != "arrived":
            target = navigation["target"]
            state = (
                f'{navigation["status"].capitalize()} → '
                f'({target["x"]}, {target["y"]}) · '
                f'{len(navigation["path"])} celle'
            )
        elif area is not None:
            state = f"In attività · {area}"
        else:
            state = "In attesa"
        state_class = "staff-active" if active else "staff-idle"
        cards.append(
            f'<div class="staff-chip {state_class}" '
            f'style="border-left:5px solid {path_colors[agent["id"]]}">'
            f'<span class="staff-dot" style="background:{ROLE_COLORS[agent["role"]]}">'
            f'{ROLE_INITIALS[agent["role"]]}</span>'
            f'<span><strong>{escape(agent["id"])}</strong>'
            f'<small>{escape(state)}</small></span></div>'
        )
    return '<div class="staff-roster">' + "".join(cards) + "</div>"


def render_area_access(snapshot: dict) -> str:
    cards = []
    for access in snapshot.get("room_occupancy", snapshot["area_access"]):
        current = len(access["occupants"])
        capacity = access["capacity"]
        tone = "room-full" if current == capacity else "room-free"
        occupants = ", ".join(access["occupants"]) or "Nessun operatore"
        cards.append(
            f'<div class="room-access {tone}">'
            f'<span><strong>{escape(access["area_id"])}</strong>'
            f'<small>{escape(occupants)}</small></span>'
            f'<b>{current}/{capacity}</b></div>'
        )
    return '<div class="room-access-grid">' + "".join(cards) + "</div>"


def _agent_path_colors(snapshot: dict) -> dict[str, str]:
    return {
        agent["id"]: PATH_COLORS[index % len(PATH_COLORS)]
        for index, agent in enumerate(sorted(snapshot["agents"], key=lambda item: item["id"]))
    }


def render_placeholder_svg() -> str:
    return (
        f'<svg viewBox="0 0 {GRID_WIDTH} {GRID_HEIGHT}" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<rect width="100%" height="100%" rx="18" fill="#f8fafc"/>'
        f'<text x="{GRID_WIDTH / 2}" y="{GRID_HEIGHT / 2 - 8}" '
        'text-anchor="middle" font-family="Inter,Segoe UI,sans-serif" '
        'font-size="22" font-weight="800" fill="#334155">'
        'Connessione al Visualization Agent SPADE</text>'
        f'<text x="{GRID_WIDTH / 2}" y="{GRID_HEIGHT / 2 + 24}" '
        'text-anchor="middle" font-family="Inter,Segoe UI,sans-serif" '
        'font-size="13" fill="#64748b">In attesa dello snapshot iniziale…</text>'
        '</svg>'
    )
