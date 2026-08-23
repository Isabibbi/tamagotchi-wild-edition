
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import ceil, sqrt


FLOORPLAN_WIDTH = 1120
FLOORPLAN_HEIGHT = 720

ROLE_COLORS = {
    "veterinary": "#1677c8",
    "logistics": "#7047a8",
    "feeding": "#dc6b21",
}
ROLE_LABELS = {
    "veterinary": "Veterinary",
    "logistics": "Logistics",
    "feeding": "Feeding",
}
ROLE_INITIALS = {"veterinary": "V", "logistics": "L", "feeding": "F"}
HEALTH_COLORS = {
    "sick": "#dc2626",
    "in_outbound_transport": "#7c3aed",
    "in_treatment": "#d97706",
    "treated": "#0284c7",
    "in_return_transport": "#7c3aed",
    "healthy": "#16a34a",
}
HEALTH_LABELS = {
    "sick": "Sick",
    "in_outbound_transport": "Going to treatment",
    "in_treatment": "In treatment",
    "treated": "Treated",
    "in_return_transport": "Returning to cage",
    "healthy": "Healthy",
}
SPECIES_SYMBOLS = {
    "fox": "&#x1F98A;",
    "owl": "&#x1F989;",
    "hedgehog": "&#x1F994;",
    "badger": "&#x1F9A1;",
    "hare": "&#x1F407;",
    "deer": "&#x1F98C;",
    "squirrel": "&#x1F43F;&#xFE0F;",
    "tortoise": "&#x1F422;",
    "heron": "&#x1F426;",
    "bat": "&#x1F987;",
}

ROOM_RECTS = {
    "food-storage": (28, 28, 390, 210),
    "medical-storage": (702, 28, 390, 210),
    "cage-area": (28, 318, 650, 374),
    "treatment-room": (702, 318, 390, 374),
}
ROOM_OPERATOR_POINTS = {
    "food-storage": ((165, 176), (282, 176)),
    "medical-storage": ((815, 176), (942, 176)),
    "cage-area": ((520, 470), (604, 470)),
    "treatment-room": ((814, 520), (964, 520)),
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
        active_operators=sum(
            len(access["occupants"]) for access in snapshot["area_access"]
        ),
    )


def render_floorplan_svg(
    snapshot: dict,
    previous_snapshot: dict | None = None,
    transition_seconds: float = 0.18,
) -> str:

    current_points = _agent_points(snapshot)
    previous_points = (
        _agent_points(previous_snapshot) if previous_snapshot is not None else {}
    )
    active_areas = _area_for_agent(snapshot)
    cage_layout = _cage_layout(snapshot["cages"])
    animals_by_id = {animal["id"]: animal for animal in snapshot["animals"]}
    agents_by_id = {agent["id"]: agent for agent in snapshot["agents"]}
    duration = min(1.2, max(0.10, transition_seconds))

    chunks = [
        f'<svg viewBox="0 0 {FLOORPLAN_WIDTH} {FLOORPLAN_HEIGHT}" '
        'role="img" aria-label="Illustrated floorplan of the rescue centre" '
        'xmlns="http://www.w3.org/2000/svg">',
        _svg_definitions(),
        '<rect width="1120" height="720" rx="28" fill="#d8e1dc"/>',
        '<rect x="12" y="12" width="1096" height="696" rx="24" '
        'fill="#eee9df" stroke="#4b5563" stroke-width="8"/>',
        _render_hallway(),
        _render_food_storage(snapshot),
        _render_medical_storage(snapshot),
        _render_cage_room(),
        _render_treatment_room(),
        _render_room_occupancy(snapshot),
    ]

    for cage in snapshot["cages"]:
        animal = animals_by_id.get(cage["animal_id"])
        bowl = next(
            (item for item in snapshot["bowls"] if item["id"] == cage["bowl_id"]),
            None,
        )
        animal_in_cage = (
            animal is not None
            and animal["carried_by"] is None
            and _area_kind_at(snapshot, animal["position"]) == "cage_area"
        )
        chunks.append(
            _render_cage(
                cage,
                cage_layout[cage["id"]],
                animal if animal_in_cage else None,
                bowl,
            )
        )

    treatment_animals = [
        animal
        for animal in snapshot["animals"]
        if animal["carried_by"] is None
        and _area_kind_at(snapshot, animal["position"]) == "treatment_room"
    ]
    for index, animal in enumerate(treatment_animals):
        chunks.append(_render_treatment_animal(animal, index))

    for index, agent in enumerate(
        sorted(snapshot["agents"], key=lambda item: item["id"])
    ):
        agent_id = agent["id"]
        current = current_points[agent_id]
        previous = previous_points.get(agent_id, current)
        chunks.append(
            _render_operator(
                agent,
                current,
                previous,
                snapshot,
                duration,
                index,
            )
        )
        carried_animals = [
            animal
            for animal in snapshot["animals"]
            if animal["carried_by"] == agent_id
        ]
        for carried_index, animal in enumerate(carried_animals):
            chunks.append(
                _render_carried_animal(
                    animal,
                    current,
                    previous,
                    duration,
                    carried_index,
                )
            )

    chunks.append("</svg>")
    return "".join(chunks)


def render_grid_svg(snapshot: dict) -> str:

    return render_floorplan_svg(snapshot)


def _svg_definitions() -> str:
    return """
    <defs>
      <linearGradient id="hallFloor" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#f4efe6"/><stop offset="1" stop-color="#d9d1c3"/>
      </linearGradient>
      <linearGradient id="foodFloor" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#fff7d6"/><stop offset="1" stop-color="#eadcaa"/>
      </linearGradient>
      <linearGradient id="medicalFloor" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#eaf6ff"/><stop offset="1" stop-color="#c8dfed"/>
      </linearGradient>
      <linearGradient id="cageFloor" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#e8f2df"/><stop offset="1" stop-color="#c3d5b7"/>
      </linearGradient>
      <linearGradient id="treatmentFloor" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#f7f9fb"/><stop offset="1" stop-color="#d7e4e8"/>
      </linearGradient>
      <linearGradient id="steel" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#4b5563"/><stop offset=".5" stop-color="#cbd5e1"/><stop offset="1" stop-color="#475569"/>
      </linearGradient>
      <filter id="roomShadow" x="-15%" y="-15%" width="130%" height="140%">
        <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#1f2937" flood-opacity=".18"/>
      </filter>
      <filter id="objectShadow" x="-30%" y="-30%" width="160%" height="170%">
        <feDropShadow dx="0" dy="5" stdDeviation="4" flood-color="#111827" flood-opacity=".28"/>
      </filter>
      <style>
        .room-title { font: 800 17px Inter,Segoe UI,sans-serif; fill:#172033; letter-spacing:.7px; }
        .room-subtitle { font: 600 10px Inter,Segoe UI,sans-serif; fill:#64748b; letter-spacing:.8px; }
        .floor-note { font: 650 10px Inter,Segoe UI,sans-serif; fill:#475569; }
        .tiny-label { font: 750 9px Inter,Segoe UI,sans-serif; fill:#334155; }
        .operator-name { font: 800 9px Inter,Segoe UI,sans-serif; fill:#172033; }
        .operator-role { font: 650 7px Inter,Segoe UI,sans-serif; fill:#64748b; }
        .operator { filter:url(#objectShadow); }
        .operator-walking .human-leg-left,
        .operator-walking .human-arm-right { transform-box:fill-box; transform-origin:top center; animation:limbForward .18s ease-in-out infinite alternate; }
        .operator-walking .human-leg-right,
        .operator-walking .human-arm-left { transform-box:fill-box; transform-origin:top center; animation:limbBack .18s ease-in-out infinite alternate; }
        @keyframes limbForward { from { transform:rotate(-18deg); } to { transform:rotate(20deg); } }
        @keyframes limbBack { from { transform:rotate(18deg); } to { transform:rotate(-20deg); } }
      </style>
    </defs>
    """


def _render_hallway() -> str:
    return """
    <g aria-label="Central corridor">
      <path d="M18 238H1102V318H18Z M418 18H702V318H418Z" fill="url(#hallFloor)"/>
      <path d="M34 276H1086" stroke="#c1b9ab" stroke-width="2" stroke-dasharray="18 16" opacity=".6"/>
      <rect x="481" y="84" width="158" height="72" rx="12" fill="#7c573b" filter="url(#objectShadow)"/>
      <rect x="491" y="94" width="138" height="45" rx="8" fill="#a97953"/>
      <rect x="516" y="54" width="88" height="48" rx="6" fill="#263747"/>
      <rect x="522" y="60" width="76" height="36" rx="3" fill="#bde3df"/>
      <path d="M545 139v20m30-20v20" stroke="#4b3425" stroke-width="7"/>
      <text x="560" y="181" text-anchor="middle" class="tiny-label">STAFF STATION</text>
      <g transform="translate(36 256)">
        <rect width="156" height="39" rx="18" fill="#ffffff" opacity=".8"/>
        <circle cx="21" cy="19" r="11" fill="#16a34a"/>
        <path d="M17 19l3 3 6-7" fill="none" stroke="white" stroke-width="3"/>
        <text x="42" y="23" class="floor-note">Operational corridor</text>
      </g>
    </g>
    """


def _room_frame(
    room_id: str,
    fill: str,
    title: str,
    subtitle: str,
    icon: str,
) -> str:
    x, y, width, height = ROOM_RECTS[room_id]
    return (
        f'<g aria-label="{escape(title)}">'
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="18" '
        f'fill="{fill}" stroke="#344454" stroke-width="8" filter="url(#roomShadow)"/>'
        f'<rect x="{x + 16}" y="{y + 14}" width="{width - 32}" height="43" rx="11" '
        'fill="#ffffff" fill-opacity=".82"/>'
        f'<circle cx="{x + 40}" cy="{y + 35}" r="15" fill="#ffffff"/>'
        f'<text x="{x + 40}" y="{y + 42}" text-anchor="middle" font-size="20">{icon}</text>'
        f'<text x="{x + 64}" y="{y + 32}" class="room-title">{escape(title)}</text>'
        f'<text x="{x + 64}" y="{y + 47}" class="room-subtitle">{escape(subtitle)}</text>'
        '</g>'
    )


def _render_food_storage(snapshot: dict) -> str:
    quantity = snapshot["food"][0]["quantity"] if snapshot["food"] else 0
    return _room_frame(
        "food-storage",
        "url(#foodFloor)",
        "FOOD STORAGE",
        f"AVAILABLE STOCK: {quantity}",
        "&#x1F35A;",
    ) + """
    <g aria-label="Shelves and containers in the food storage">
      <rect x="52" y="92" width="78" height="112" rx="5" fill="#76533a"/>
      <path d="M58 122h66M58 156h66M78 92v112M105 92v112" stroke="#d5b184" stroke-width="5"/>
      <g fill="#b7793f" stroke="#724b2b" stroke-width="2">
        <path d="M153 151q24-15 48 0l-5 51h-38z"/>
        <path d="M213 148q24-14 48 0l-5 54h-38z"/>
      </g>
      <path d="M161 160h32M221 157h32" stroke="#f4d6a7" stroke-width="4"/>
      <rect x="294" y="88" width="96" height="116" rx="8" fill="#e7ecef" stroke="#64748b" stroke-width="4"/>
      <path d="M342 91v110M304 128h76" stroke="#94a3b8" stroke-width="3"/>
      <circle cx="332" cy="110" r="3" fill="#475569"/><circle cx="352" cy="145" r="3" fill="#475569"/>
    </g>
    """


def _render_medical_storage(snapshot: dict) -> str:
    quantity = snapshot["medicine"][0]["quantity"] if snapshot["medicine"] else 0
    return _room_frame(
        "medical-storage",
        "url(#medicalFloor)",
        "MEDICAL STORAGE",
        f"MEDICINE AVAILABLE: {quantity}",
        "&#x2695;",
    ) + """
    <g aria-label="Cabinets and medical equipment">
      <rect x="724" y="86" width="100" height="120" rx="8" fill="#f8fafc" stroke="#7894a4" stroke-width="4"/>
      <path d="M774 88v116M731 136h86" stroke="#b6c8d2" stroke-width="3"/>
      <path d="M764 111h20m-10-10v20" stroke="#e04848" stroke-width="7" stroke-linecap="round"/>
      <rect x="850" y="104" width="98" height="102" rx="5" fill="#8fa7b4"/>
      <path d="M858 130h82M858 162h82" stroke="#dbe8ee" stroke-width="5"/>
      <g fill="#f8fafc" stroke="#4f7182" stroke-width="2">
        <rect x="864" y="113" width="17" height="12" rx="2"/>
        <rect x="889" y="108" width="17" height="17" rx="2"/>
        <rect x="914" y="115" width="17" height="10" rx="2"/>
      </g>
      <rect x="971" y="91" width="91" height="115" rx="7" fill="#e4eef3" stroke="#7894a4" stroke-width="4"/>
      <circle cx="1017" cy="149" r="24" fill="#b9dce8"/><path d="M1007 149h20m-10-10v20" stroke="#ffffff" stroke-width="6"/>
    </g>
    """


def _render_cage_room() -> str:
    return _room_frame(
        "cage-area",
        "url(#cageFloor)",
        "CAGE AREA",
        "SHELTER AND ANIMAL OBSERVATION",
        "&#x25A6;",
    ) + """
    <g class="cage-bowl-legend" transform="translate(452 340)"
       aria-label="Bowl legend: green full, red empty">
      <rect width="126" height="25" rx="12" fill="#ffffff" opacity=".9"/>
      <circle cx="13" cy="12.5" r="5" fill="#22c55e"/>
      <text x="22" y="16" class="tiny-label">FULL</text>
      <circle cx="70" cy="12.5" r="5" fill="#ef4444"/>
      <text x="79" y="16" class="tiny-label">EMPTY</text>
    </g>
    <g opacity=".8">
      <rect x="49" y="381" width="607" height="287" rx="14" fill="#f6f2e7"/>
      <path d="M62 650q75-42 150 0t150 0t150 0t130 0v18H62z" fill="#9eb48d" opacity=".45"/>
    </g>
    """


def _render_treatment_room() -> str:
    return _room_frame(
        "treatment-room",
        "url(#treatmentFloor)",
        "TREATMENT ROOM",
        "MAX 3 PATIENTS · PRIORITY CARE",
        "&#x1FA7A;",
    ) + """
    <g aria-label="Bed and equipment in the treatment room">
      <rect x="785" y="441" width="190" height="78" rx="28" fill="#d8eef0" stroke="#50808a" stroke-width="5" filter="url(#objectShadow)"/>
      <path d="M810 515v47M948 515v47" stroke="#50636b" stroke-width="9"/>
      <circle cx="810" cy="567" r="8" fill="#334155"/><circle cx="948" cy="567" r="8" fill="#334155"/>
      <rect x="1000" y="389" width="62" height="86" rx="8" fill="#263747"/>
      <rect x="1007" y="398" width="48" height="53" rx="4" fill="#9be5d4"/>
      <path d="M1012 426h10l6-14 8 28 7-14h9" fill="none" stroke="#167b68" stroke-width="3"/>
      <path d="M1031 475v63M1013 538h36" stroke="#52636e" stroke-width="7"/>
      <path d="M748 398v138M733 398h30M739 420h18" stroke="#637681" stroke-width="5"/>
      <path d="M739 420q3 28 15 34" fill="none" stroke="#7dd3fc" stroke-width="3"/>
      <rect x="1002" y="586" width="62" height="70" rx="7" fill="#d7e5e8" stroke="#76909a" stroke-width="3"/>
      <path d="M1014 602h38M1033 588v68" stroke="#9bb0b8" stroke-width="3"/>
    </g>
    """


def _render_room_occupancy(snapshot: dict) -> str:
    chunks = []
    treatment = snapshot.get("treatment", {})
    for access in snapshot["area_access"]:
        room = ROOM_RECTS.get(access["area_id"])
        if room is None:
            continue
        x, y, width, _ = room
        count = len(access["occupants"])
        tone = "#dc2626" if count == access["capacity"] else "#16a34a"
        chunks.append(
            f'<g transform="translate({x + width - 83} {y + 23})">'
            '<rect width="64" height="25" rx="12" fill="#ffffff" opacity=".92"/>'
            f'<circle cx="15" cy="12.5" r="6" fill="{tone}"/>'
            f'<text x="28" y="17" class="tiny-label">{count}/{access["capacity"]}</text>'
            '</g>'
        )
        if access["area_id"] == "treatment-room":
            patient_count = treatment.get("patient_count", 0)
            patient_capacity = treatment.get("patient_capacity", 3)
            patient_tone = (
                "#dc2626"
                if patient_count == patient_capacity
                else "#0f766e"
            )
            chunks.append(
                f'<g transform="translate({x + width - 166} {y + 23})">'
                '<rect width="76" height="25" rx="12" fill="#ffffff" opacity=".92"/>'
                f'<circle cx="15" cy="12.5" r="6" fill="{patient_tone}"/>'
                f'<text x="27" y="17" class="tiny-label">P {patient_count}/{patient_capacity}</text>'
                '</g>'
            )
    return "".join(chunks)


def _cage_layout(cages: list[dict]) -> dict[str, tuple[float, float, float, float]]:
    count = max(1, len(cages))
    columns = min(8, max(1, ceil(sqrt(count * 1.55))))
    rows = ceil(count / columns)
    content_x, content_y, content_width, content_height = 50, 392, 606, 258
    slot_width = content_width / columns
    slot_height = content_height / rows
    cage_width = min(182, max(54, slot_width - 12))
    cage_height = min(112, max(42, slot_height - 12))
    layout = {}
    for index, cage in enumerate(sorted(cages, key=lambda item: item["id"])):
        row, column = divmod(index, columns)
        x = content_x + column * slot_width + (slot_width - cage_width) / 2
        y = content_y + row * slot_height + (slot_height - cage_height) / 2
        layout[cage["id"]] = (x, y, cage_width, cage_height)
    return layout


def _render_cage(
    cage: dict,
    bounds: tuple[float, float, float, float],
    animal: dict | None,
    bowl: dict | None,
) -> str:
    x, y, width, height = bounds
    cage_id = escape(cage["id"])
    bar_count = min(9, max(3, int(width // 22)))
    bar_step = width / (bar_count + 1)
    bars = "".join(
        f'<line class="cage-bar" x1="{x + bar_step * index:.1f}" y1="{y + 8:.1f}" '
        f'x2="{x + bar_step * index:.1f}" y2="{y + height - 7:.1f}" '
        'stroke="#52616a" stroke-width="3.5"/>'
        for index in range(1, bar_count + 1)
    )
    crossbars = (
        f'<line class="cage-crossbar" x1="{x + 5:.1f}" y1="{y + height * .36:.1f}" '
        f'x2="{x + width - 5:.1f}" y2="{y + height * .36:.1f}" '
        'stroke="#3f4d55" stroke-width="4"/>'
        f'<line class="cage-crossbar" x1="{x + 5:.1f}" y1="{y + height * .72:.1f}" '
        f'x2="{x + width - 5:.1f}" y2="{y + height * .72:.1f}" '
        'stroke="#3f4d55" stroke-width="4"/>'
    )
    animal_markup = ""
    if animal is not None:
        symbol = SPECIES_SYMBOLS.get(animal["species"], "&#x1F43E;")
        animal_markup = (
            f'<circle cx="{x + width / 2:.1f}" cy="{y + height * .58:.1f}" '
            f'r="{min(25, height * .23):.1f}" fill="#ffffff" stroke="{HEALTH_COLORS.get(animal["health"], "#64748b")}" stroke-width="4"/>'
            f'<text x="{x + width / 2:.1f}" y="{y + height * .58 + 8:.1f}" '
            f'text-anchor="middle" font-size="{min(30, height * .30):.1f}">{symbol}</text>'
        )
    bowl_full = bowl is not None and bowl["level"] == bowl["capacity"]
    bowl_color = "#22c55e" if bowl_full else "#ef4444"
    bowl_state = "full" if bowl_full else "empty"
    bowl_x = x + width - 22
    bowl_y = y + height - 12
    food_marks = (
        f'<circle cx="{bowl_x - 5:.1f}" cy="{bowl_y - 4:.1f}" r="2" fill="#fef3c7"/>'
        f'<circle cx="{bowl_x + 1:.1f}" cy="{bowl_y - 5:.1f}" r="2" fill="#fef3c7"/>'
        f'<circle cx="{bowl_x + 6:.1f}" cy="{bowl_y - 3:.1f}" r="2" fill="#fef3c7"/>'
        if bowl_full
        else ""
    )
    return (
        f'<g class="animal-cage" data-cage-id="{cage_id}">'
        f'<title>{cage_id} · bowl {bowl_state}</title>'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="9" '
        'fill="#e9dfca" stroke="#35434b" stroke-width="6" filter="url(#objectShadow)"/>'
        f'<rect x="{x + 6:.1f}" y="{y + 7:.1f}" width="{width - 12:.1f}" height="{height - 14:.1f}" rx="5" fill="#f8f4e9"/>'
        f'{animal_markup}{bars}{crossbars}'
        f'<rect x="{x + 8:.1f}" y="{y - 11:.1f}" width="{min(width - 16, 88):.1f}" height="22" rx="7" fill="#35434b"/>'
        f'<text x="{x + 15:.1f}" y="{y + 4:.1f}" font-family="Inter,Segoe UI,sans-serif" font-size="9" font-weight="800" fill="#ffffff">{cage_id}</text>'
        f'<rect x="{x + width - 21:.1f}" y="{y + height * .38:.1f}" width="12" height="22" rx="3" fill="#d6a43d" stroke="#6b4f17" stroke-width="2"/>'
        f'<g class="cage-bowl" data-state="{bowl_state}" '
        f'aria-label="Bowl {bowl_state}">'  
        f'<title>Bowl {bowl_state}</title>'
        f'<path d="M{bowl_x - 14:.1f} {bowl_y - 2:.1f} '
        f'Q{bowl_x:.1f} {bowl_y + 5:.1f} {bowl_x + 14:.1f} {bowl_y - 2:.1f} '
        f'L{bowl_x + 10:.1f} {bowl_y + 9:.1f} '
        f'Q{bowl_x:.1f} {bowl_y + 14:.1f} {bowl_x - 10:.1f} {bowl_y + 9:.1f}Z" '
        'fill="#d6a43d" stroke="#6b4f17" stroke-width="2"/>'
        f'<ellipse class="bowl-content" cx="{bowl_x:.1f}" cy="{bowl_y - 2:.1f}" '
        f'rx="13" ry="6" fill="{bowl_color}" stroke="#ffffff" stroke-width="2"/>'
        f'{food_marks}</g>'
        '</g>'
    )


def _agent_points(snapshot: dict | None) -> dict[str, tuple[float, float]]:
    if snapshot is None:
        return {}
    agents = sorted(snapshot["agents"], key=lambda item: item["id"])
    area_for_agent = _area_for_agent(snapshot)
    access_by_area = {
        access["area_id"]: sorted(access["occupants"])
        for access in snapshot["area_access"]
    }
    points: dict[str, tuple[float, float]] = {}
    waiting_start = 244
    waiting_step = 104
    for index, agent in enumerate(agents):
        area_id = area_for_agent.get(agent["id"])
        if area_id in ROOM_OPERATOR_POINTS:
            occupants = access_by_area[area_id]
            local_index = occupants.index(agent["id"])
            room_points = ROOM_OPERATOR_POINTS[area_id]
            points[agent["id"]] = room_points[local_index % len(room_points)]
        else:
            points[agent["id"]] = (waiting_start + index * waiting_step, 296)
    return points


def _area_for_agent(snapshot: dict) -> dict[str, str]:
    return {
        agent_id: access["area_id"]
        for access in snapshot["area_access"]
        for agent_id in access["occupants"]
    }


STATUS_COLORS = {
    "free": "#16a34a",
    "busy": "#dc2626",
    "waiting": "#64748b",
}
STATUS_LABELS = {
    "free": "Free",
    "busy": "Busy",
    "waiting": "Waiting",
}


def _operator_status(agent: dict, snapshot: dict) -> tuple[str, str, str]:
    agent_id = agent["id"]
    area_id = _area_for_agent(snapshot).get(agent_id)
    is_carrying = any(
        animal.get("carried_by") == agent_id
        for animal in snapshot.get("animals", [])
    )
    if area_id is not None or is_carrying:
        return "busy", STATUS_LABELS["busy"], STATUS_COLORS["busy"]

    tasks = snapshot.get("tasks", [])
    all_completed = bool(tasks) and all(t.get("status") == "completed" for t in tasks)
    if all_completed:
        return "free", STATUS_LABELS["free"], STATUS_COLORS["free"]

    has_assigned_active = any(
        t.get("assigned_to") == agent_id
        and t.get("status") in ("assigned", "in_progress", "pending")
        for t in tasks
    )
    if has_assigned_active:
        return "waiting", STATUS_LABELS["waiting"], STATUS_COLORS["waiting"]

    return "free", STATUS_LABELS["free"], STATUS_COLORS["free"]


def _render_operator(
    agent: dict,
    current: tuple[float, float],
    previous: tuple[float, float],
    snapshot: dict,
    duration: float,
    index: int,
) -> str:
    agent_id = escape(agent["id"])
    role = agent["role"]
    color = ROLE_COLORS[role]
    area_id = _area_for_agent(snapshot).get(agent["id"])
    status_key, status_label, status_color = _operator_status(agent, snapshot)
    moving = current != previous
    css_class = (
        f"operator operator-walking operator-{status_key}"
        if moving
        else f"operator operator-{status_key}"
    )
    skin = ("#f2c6a0", "#c98e68", "#8c5a3c")[index % 3]
    hair = ("#38251c", "#6c432e", "#1f2937", "#a56a3a")[index % 4]
    animation = ""
    if moving:
        animation = (
            '<animateTransform attributeName="transform" type="translate" '
            f'from="{previous[0]:.1f} {previous[1]:.1f}" '
            f'to="{current[0]:.1f} {current[1]:.1f}" dur="{duration:.2f}s" '
            'calcMode="spline" keySplines="0.22 1 0.36 1" fill="freeze"/>'
        )
    if status_key == "busy":
        status_halo = (
            f'<circle cx="0" cy="-28" r="30" fill="{status_color}" opacity=".26">'
            '<animate attributeName="r" values="28;35;28" dur="1.2s" repeatCount="indefinite"/>'
            '</circle>'
        )
    elif status_key == "waiting":
        status_halo = (
            f'<circle cx="0" cy="-28" r="28" fill="{status_color}" opacity=".22"/>'
        )
    else:
        status_halo = (
            f'<circle cx="0" cy="-28" r="28" fill="{status_color}" opacity=".20"/>'
        )

    accessory = _role_accessory(role)
    state_desc = f"{status_label} · {area_id}" if area_id else status_label
    return (
        f'<g class="{css_class}" data-agent-id="{agent_id}" '
        f'transform="translate({current[0]:.1f} {current[1]:.1f})">'
        f'<title>{agent_id} · {escape(ROLE_LABELS[role])} · {escape(state_desc)}</title>'
        f'{animation}{status_halo}'
        '<ellipse cx="0" cy="2" rx="19" ry="6" fill="#172033" opacity=".22"/>'
        '<g class="human-figure">'
        f'<g class="human-leg-left"><path d="M-7-24L-9-3" stroke="{color}" stroke-width="8" stroke-linecap="round"/><path d="M-9-3l-7 2" stroke="#263747" stroke-width="6" stroke-linecap="round"/></g>'
        f'<g class="human-leg-right"><path d="M7-24L9-3" stroke="{color}" stroke-width="8" stroke-linecap="round"/><path d="M9-3l7 2" stroke="#263747" stroke-width="6" stroke-linecap="round"/></g>'
        f'<path d="M-14-52Q0-60 14-52L12-23Q0-17-12-23Z" fill="{color}" stroke="#ffffff" stroke-width="2"/>'
        f'<g class="human-arm-left"><path d="M-12-49L-20-29" stroke="{color}" stroke-width="7" stroke-linecap="round"/><circle cx="-21" cy="-27" r="4" fill="{skin}"/></g>'
        f'<g class="human-arm-right"><path d="M12-49L20-29" stroke="{color}" stroke-width="7" stroke-linecap="round"/><circle cx="21" cy="-27" r="4" fill="{skin}"/></g>'
        f'<rect x="-4" y="-63" width="8" height="8" rx="3" fill="{skin}"/>'
        f'<circle class="human-head" cx="0" cy="-69" r="12" fill="{skin}" stroke="#ffffff" stroke-width="2"/>'
        f'<path d="M-11-72q2-14 13-12 9 1 10 13-11-7-23-1z" fill="{hair}"/>'
        '<circle cx="-4" cy="-68" r="1.2" fill="#263747"/><circle cx="4" cy="-68" r="1.2" fill="#263747"/>'
        '<path d="M-3-63q3 2 6 0" fill="none" stroke="#8b4b3b" stroke-width="1.5" stroke-linecap="round"/>'
        f'<circle cx="0" cy="-44" r="8" fill="#ffffff"/><text x="0" y="-41" text-anchor="middle" font-family="Inter,Segoe UI,sans-serif" font-size="8" font-weight="900" fill="{color}">{ROLE_INITIALS[role]}</text>'
        f'{accessory}'
        '</g>'
        '<g transform="translate(-55 -108)">'
        f'<rect width="110" height="31" rx="9" fill="#ffffff" stroke="{status_color}" stroke-width="2.5"/>'
        f'<circle cx="12" cy="15.5" r="4" fill="{status_color}"/>'
        f'<text x="58" y="13" text-anchor="middle" class="operator-name">{agent_id}</text>'
        f'<text x="58" y="24" text-anchor="middle" class="operator-role">{escape(ROLE_LABELS[role])} · {status_label}</text>'
        '</g></g>'
    )


def _role_accessory(role: str) -> str:
    if role == "veterinary":
        return (
            '<path d="M-8-51v12q0 8 8 8t8-8v-12" fill="none" stroke="#dbeafe" stroke-width="2"/>'
            '<circle cx="8" cy="-38" r="3" fill="#dbeafe"/>'
        )
    if role == "logistics":
        return (
            '<path d="M-12-42h24M-11-35h22" stroke="#facc15" stroke-width="3" opacity=".9"/>'
            '<path d="M-9-81q9-7 18 0l4 5h-26z" fill="#4c3276"/>'
        )
    return (
        '<path d="M-9-49L-7-25H7L9-49" fill="#fff7ed" opacity=".9"/>'
        '<rect x="-5" y="-36" width="10" height="7" rx="2" fill="#f4b183"/>'
    )


def _render_carried_animal(
    animal: dict,
    current: tuple[float, float],
    previous: tuple[float, float],
    duration: float,
    index: int,
) -> str:
    current_position = (current[0] + 28 + index * 13, current[1] - 34)
    previous_position = (previous[0] + 28 + index * 13, previous[1] - 34)
    symbol = SPECIES_SYMBOLS.get(animal["species"], "&#x1F43E;")
    animation = ""
    if current_position != previous_position:
        animation = (
            '<animateTransform attributeName="transform" type="translate" '
            f'from="{previous_position[0]:.1f} {previous_position[1]:.1f}" '
            f'to="{current_position[0]:.1f} {current_position[1]:.1f}" '
            f'dur="{duration:.2f}s" fill="freeze"/>'
        )
    return (
        f'<g class="carried-animal" transform="translate({current_position[0]:.1f} {current_position[1]:.1f})">'
        f'<title>{escape(animal["id"])} being transported</title>{animation}'
        '<rect x="-18" y="-15" width="36" height="30" rx="8" fill="#caa675" stroke="#654b2d" stroke-width="3"/>'
        f'<text x="0" y="8" text-anchor="middle" font-size="24">{symbol}</text>'
        '</g>'
    )


def _render_treatment_animal(animal: dict, index: int) -> str:
    x = 858 + (index % 2) * 58
    y = 468 + (index // 2) * 42
    symbol = SPECIES_SYMBOLS.get(animal["species"], "&#x1F43E;")
    color = HEALTH_COLORS.get(animal["health"], "#64748b")
    return (
        f'<g class="treatment-animal" transform="translate({x} {y})">'
        f'<title>{escape(animal["id"])} · {escape(HEALTH_LABELS.get(animal["health"], animal["health"]))}</title>'
        f'<circle r="25" fill="#ffffff" stroke="{color}" stroke-width="5"/>'
        f'<text x="0" y="9" text-anchor="middle" font-size="30">{symbol}</text>'
        '</g>'
    )


def _area_kind_at(snapshot: dict, position: dict) -> str | None:
    coordinates = (position["x"], position["y"])
    for area in snapshot["areas"]:
        if any((cell["x"], cell["y"]) == coordinates for cell in area["cells"]):
            return area["kind"]
    return None


def render_operator_roster(snapshot: dict) -> str:
    cards = []
    for agent in snapshot["agents"]:
        status_key, status_label, status_color = _operator_status(agent, snapshot)
        area = _area_for_agent(snapshot).get(agent["id"])
        if status_key == "busy":
            state = f"Busy · {area}" if area else "Busy"
            state_class = "staff-chip staff-active staff-busy"
        elif status_key == "waiting":
            state = "Waiting"
            state_class = "staff-chip staff-idle staff-waiting"
        else:
            state = "Free"
            state_class = "staff-chip staff-idle staff-free"
        cards.append(
            f'<div class="staff-chip {state_class}">'
            f'<span class="staff-person" style="--uniform:{ROLE_COLORS[agent["role"]]}">'
            '<i class="staff-head"></i><i class="staff-body"></i></span>'
            f'<span><strong>{escape(agent["id"])}</strong>'
            f'<small>{escape(ROLE_LABELS[agent["role"]])} · <span style="color:{status_color};font-weight:700">{escape(state)}</span></small></span></div>'
        )
    return '<div class="staff-roster">' + "".join(cards) + "</div>"


def render_area_access(snapshot: dict) -> str:
    cards = []
    labels = {
        "food-storage": "Food storage",
        "medical-storage": "Medical storage",
        "cage-area": "Cage area",
        "treatment-room": "Treatment room",
    }
    for access in snapshot["area_access"]:
        current = len(access["occupants"])
        capacity = access["capacity"]
        tone = "room-full" if current == capacity else "room-free"
        occupants = ", ".join(access["occupants"]) or "No operators"
        detail = occupants
        if access["area_id"] == "treatment-room":
            treatment = snapshot.get("treatment", {})
            detail = (
                f'Patients {treatment.get("patient_count", 0)}/'
                f'{treatment.get("patient_capacity", 3)} · {occupants}'
            )
        cards.append(
            f'<div class="room-access {tone}">'
            f'<span><strong>{escape(labels.get(access["area_id"], access["area_id"]))}</strong>'
            f'<small>{escape(detail)}</small></span>'
            f'<b>{current}/{capacity}</b></div>'
        )
    return '<div class="room-access-grid">' + "".join(cards) + "</div>"


def render_placeholder_svg() -> str:
    return (
        f'<svg viewBox="0 0 {FLOORPLAN_WIDTH} {FLOORPLAN_HEIGHT}" '
        'role="img" aria-label="Rescue centre floorplan loading" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<rect width="100%" height="100%" rx="24" fill="#e6ebe7"/>'
        '<path d="M170 190h780v350H170z" fill="#ffffff" stroke="#52636b" stroke-width="10"/>'
        '<path d="M560 190v350M170 360h780" stroke="#9aa9ad" stroke-width="7"/>'
        f'<text x="{FLOORPLAN_WIDTH / 2}" y="{FLOORPLAN_HEIGHT / 2 - 20}" '
        'text-anchor="middle" font-family="Inter,Segoe UI,sans-serif" '
        'font-size="24" font-weight="800" fill="#334155">'
        'Connecting to Visualization Agent SPADE</text>'
        f'<text x="{FLOORPLAN_WIDTH / 2}" y="{FLOORPLAN_HEIGHT / 2 + 18}" '
        'text-anchor="middle" font-family="Inter,Segoe UI,sans-serif" '
        'font-size="14" fill="#64748b">Preparing the centre floorplan…</text>'
        '</svg>'
    )
