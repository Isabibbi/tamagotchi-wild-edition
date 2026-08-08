"""Interfaccia Tkinter alimentata esclusivamente dal Visualization Agent SPADE."""

from __future__ import annotations

from multiprocessing import get_context
from queue import Empty

from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.messaging import VisualizationUpdate
from tamagotchi_wild.visualization import timeline_entries


CELL_SIZE = 58
GRID_MARGIN = 18
AREA_COLORS = {
    "food_storage": "#fff1b8",
    "medical_storage": "#cce8ff",
    "cage_area": "#d8f3dc",
    "treatment_room": "#ffd6e0",
}
AREA_LABELS = {
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
ROLE_LABELS = {"veterinary": "V", "logistics": "L", "feeding": "F"}
HEALTH_COLORS = {
    "sick": "#dc2626",
    "in_outbound_transport": "#9333ea",
    "in_treatment": "#f59e0b",
    "treated": "#0ea5e9",
    "in_return_transport": "#9333ea",
    "healthy": "#16a34a",
}


class RescueCenterGUI:
    def __init__(
        self,
        frame_queue,
        result_queue,
        config: SimulationConfig,
        step_delay_seconds: float,
    ) -> None:
        try:
            import tkinter as tk
            from tkinter import scrolledtext
        except ImportError as exc:
            raise RuntimeError("Tkinter is not available in this Python installation") from exc

        self.tk = tk
        self.frame_queue = frame_queue
        self.result_queue = result_queue
        self.config = config
        self.seen_activity_count = 0
        self.last_sequence = -1
        self.result = None
        self.pending_result = None
        self.poll_interval_ms = max(20, round(step_delay_seconds * 1000))
        self.root = tk.Tk()
        self.root.title("Tamagotchi Wild Edition — SPADE Live Simulation")
        self.root.configure(bg="#f5f7fa")
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        title = tk.Label(
            self.root,
            text="Tamagotchi Wild Edition · Simulazione SPADE-BDI",
            font=("Segoe UI", 16, "bold"),
            bg="#16324f",
            fg="white",
            padx=14,
            pady=10,
        )
        title.pack(fill="x")

        body = tk.Frame(self.root, bg="#f5f7fa")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        left = tk.Frame(body, bg="#f5f7fa")
        left.pack(side="left", fill="both", expand=False)
        right = tk.Frame(body, bg="#ffffff", bd=1, relief="solid")
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        canvas_width = 12 * CELL_SIZE + 2 * GRID_MARGIN
        canvas_height = 8 * CELL_SIZE + 2 * GRID_MARGIN
        self.canvas = tk.Canvas(
            left,
            width=canvas_width,
            height=canvas_height,
            bg="white",
            highlightthickness=1,
            highlightbackground="#94a3b8",
        )
        self.canvas.pack()

        self.status_var = tk.StringVar(value="Connessione al Visualization Agent SPADE…")
        status = tk.Label(
            left,
            textvariable=self.status_var,
            anchor="w",
            font=("Segoe UI", 10, "bold"),
            bg="#f5f7fa",
            fg="#334155",
            pady=8,
        )
        status.pack(fill="x")
        self._build_legend(left)

        summary_title = tk.Label(
            right,
            text="STATO DEL CRAS",
            font=("Segoe UI", 11, "bold"),
            bg="#ffffff",
            fg="#16324f",
            pady=8,
        )
        summary_title.pack(fill="x")
        self.summary_var = tk.StringVar(
            value=(
                f"Operatori: {config.operator_count}  ·  "
                f"Animali: {config.animal_count}\nIn attesa dello stato iniziale…"
            )
        )
        summary = tk.Label(
            right,
            textvariable=self.summary_var,
            justify="left",
            anchor="w",
            font=("Consolas", 9),
            bg="#eef4f8",
            fg="#0f172a",
            padx=10,
            pady=8,
        )
        summary.pack(fill="x", padx=8)

        timeline_title = tk.Label(
            right,
            text="CRONOLOGIA DEGLI EVENTI",
            font=("Segoe UI", 11, "bold"),
            bg="#ffffff",
            fg="#16324f",
            pady=8,
        )
        timeline_title.pack(fill="x")
        self.timeline = scrolledtext.ScrolledText(
            right,
            width=58,
            height=28,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="white",
            padx=8,
            pady=8,
        )
        self.timeline.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def run(self):
        self.root.after(self.poll_interval_ms, self._poll_updates)
        self.root.mainloop()
        return self.result

    def _build_legend(self, parent) -> None:
        legend = self.tk.Frame(parent, bg="#f5f7fa")
        legend.pack(fill="x")
        items = (
            ("Veterinary", ROLE_COLORS["veterinary"]),
            ("Logistics", ROLE_COLORS["logistics"]),
            ("Feeding", ROLE_COLORS["feeding"]),
            ("Animale malato", HEALTH_COLORS["sick"]),
            ("Animale sano", HEALTH_COLORS["healthy"]),
        )
        for label, color in items:
            item = self.tk.Frame(legend, bg="#f5f7fa")
            item.pack(side="left", padx=(0, 10))
            self.tk.Label(item, text="●", fg=color, bg="#f5f7fa").pack(side="left")
            self.tk.Label(
                item,
                text=label,
                font=("Segoe UI", 8),
                bg="#f5f7fa",
            ).pack(side="left")

    def _poll_updates(self) -> None:
        try:
            update = self.frame_queue.get_nowait()
        except Empty:
            update = None
        if update is not None:
            self._apply_update(update)

        if self.pending_result is None:
            try:
                self.pending_result = self.result_queue.get_nowait()
            except Empty:
                pass
        if update is None and self.pending_result is not None:
            result = self.pending_result
            self.pending_result = None
            if isinstance(result, Exception):
                self.status_var.set(f"SIMULAZIONE INTERROTTA: {result}")
                self._append_timeline(f"ERRORE · {result}")
            else:
                self.result = result
                outcome = "COMPLETATA" if result.success else "FALLITA"
                self.status_var.set(
                    f"SIMULAZIONE {outcome} · frame ricevuti via SPADE/XMPP"
                )
                self._append_timeline(
                    f"FINE · Feeding {result.completed_feeding_tasks}/"
                    f"{result.feeding_task_count}, Medical "
                    f"{result.completed_medical_tasks}/{result.medical_task_count}"
                )
        if self.root.winfo_exists():
            self.root.after(self.poll_interval_ms, self._poll_updates)

    def _apply_update(self, update: VisualizationUpdate) -> None:
        if update.sequence < self.last_sequence:
            return
        self.last_sequence = update.sequence
        self.status_var.set(
            f"Visualization Agent SPADE connesso · evento #{update.sequence:03d}"
        )
        self._draw_snapshot(update.snapshot)
        entries, self.seen_activity_count = timeline_entries(
            update,
            self.seen_activity_count,
        )
        for entry in entries:
            self._append_timeline(entry)

    def _draw_snapshot(self, snapshot: dict) -> None:
        self.canvas.delete("all")
        area_by_cell: dict[tuple[int, int], str] = {}
        for area in snapshot["areas"]:
            for cell in area["cells"]:
                area_by_cell[(cell["x"], cell["y"])] = area["kind"]

        for y in range(snapshot["height"]):
            for x in range(snapshot["width"]):
                x1, y1, x2, y2 = self._cell_box(x, y)
                kind = area_by_cell[(x, y)]
                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=AREA_COLORS[kind],
                    outline="#94a3b8",
                )

        for area in snapshot["areas"]:
            first = min(area["cells"], key=lambda cell: (cell["y"], cell["x"]))
            x1, y1, _, _ = self._cell_box(first["x"], first["y"])
            self.canvas.create_text(
                x1 + 5,
                y1 + 5,
                text=AREA_LABELS[area["kind"]],
                anchor="nw",
                font=("Segoe UI", 7, "bold"),
                fill="#334155",
            )

        for cage in snapshot["cages"]:
            self._draw_cage(cage)
        for bowl in snapshot["bowls"]:
            self._draw_bowl(bowl)

        agents_by_id = {agent["id"]: agent for agent in snapshot["agents"]}
        active_agents = {
            agent_id
            for access in snapshot["area_access"]
            for agent_id in access["occupants"]
        }
        agents_per_cell: dict[tuple[int, int], int] = {}
        for agent in snapshot["agents"]:
            position = agent["position"]
            cell = (position["x"], position["y"])
            local_index = agents_per_cell.get(cell, 0)
            agents_per_cell[cell] = local_index + 1
            self._draw_agent(
                agent,
                local_index,
                active=agent["id"] in active_agents,
            )
        for index, animal in enumerate(snapshot["animals"]):
            position = animal["position"]
            if animal["carried_by"] in agents_by_id:
                position = agents_by_id[animal["carried_by"]]["position"]
            self._draw_animal(animal, position, index)

        completed_feeding = sum(
            task["kind"] == "refill_bowl" and task["status"] == "completed"
            for task in snapshot["tasks"]
        )
        completed_medical = sum(
            task["kind"] == "treat_animal" and task["status"] == "completed"
            for task in snapshot["tasks"]
        )
        healthy = sum(animal["health"] == "healthy" for animal in snapshot["animals"])
        food = snapshot["food"][0]["quantity"] if snapshot["food"] else 0
        medicine = snapshot["medicine"][0]["quantity"] if snapshot["medicine"] else 0
        access_text = "  ".join(
            f"{item['area_id']}={len(item['occupants'])}/{item['capacity']}"
            for item in snapshot["area_access"]
        )
        self.summary_var.set(
            f"Animali sani: {healthy}/{len(snapshot['animals'])}   "
            f"Ciotole piene: {completed_feeding}/{len(snapshot['bowls'])}\n"
            f"Task medici: {completed_medical}/{len(snapshot['animals'])}   "
            f"Cibo: {food}   Medicinali: {medicine}\n"
            f"Accessi attivi: {access_text}"
        )

    def _draw_cage(self, cage: dict) -> None:
        position = cage["position"]
        x1, y1, x2, y2 = self._cell_box(position["x"], position["y"])
        self.canvas.create_rectangle(
            x1 + 5,
            y1 + 16,
            x2 - 5,
            y2 - 5,
            outline="#475569",
            width=2,
        )
        self.canvas.create_text(
            x1 + 7,
            y1 + 17,
            text=cage["id"],
            anchor="nw",
            font=("Segoe UI", 6, "bold"),
            fill="#475569",
        )

    def _draw_bowl(self, bowl: dict) -> None:
        position = bowl["position"]
        _, _, x2, y2 = self._cell_box(position["x"], position["y"])
        color = "#22c55e" if bowl["level"] == bowl["capacity"] else "#ef4444"
        self.canvas.create_oval(x2 - 18, y2 - 16, x2 - 7, y2 - 7, fill=color, outline="")

    def _draw_animal(self, animal: dict, position: dict, index: int) -> None:
        x1, y1, _, _ = self._cell_box(position["x"], position["y"])
        offset = (index % 3) * 4
        color = HEALTH_COLORS.get(animal["health"], "#64748b")
        self.canvas.create_oval(
            x1 + 20 + offset,
            y1 + 28,
            x1 + 40 + offset,
            y1 + 48,
            fill=color,
            outline="white",
            width=1,
        )
        self.canvas.create_text(
            x1 + 30 + offset,
            y1 + 38,
            text=animal["species"][:1].upper(),
            fill="white",
            font=("Segoe UI", 7, "bold"),
        )

    def _draw_agent(self, agent: dict, index: int, active: bool) -> None:
        position = agent["position"]
        x1, y1, _, _ = self._cell_box(position["x"], position["y"])
        offset = (index % 3) * 15
        color = ROLE_COLORS[agent["role"]]
        self.canvas.create_rectangle(
            x1 + 5 + offset,
            y1 + 4,
            x1 + 18 + offset,
            y1 + 17,
            fill=color,
            outline="#facc15" if active else "white",
            width=3 if active else 1,
        )
        self.canvas.create_text(
            x1 + 11 + offset,
            y1 + 10,
            text=ROLE_LABELS[agent["role"]],
            fill="white",
            font=("Segoe UI", 7, "bold"),
        )

    def _append_timeline(self, text: str) -> None:
        self.timeline.configure(state="normal")
        self.timeline.insert("end", f"{text}\n")
        self.timeline.see("end")
        self.timeline.configure(state="disabled")

    @staticmethod
    def _cell_box(x: int, y: int) -> tuple[int, int, int, int]:
        x1 = GRID_MARGIN + x * CELL_SIZE
        y1 = GRID_MARGIN + y * CELL_SIZE
        return x1, y1, x1 + CELL_SIZE, y1 + CELL_SIZE

    def _close(self) -> None:
        self.root.destroy()


def run_graphical_simulation(
    config: SimulationConfig,
    food: int | None,
    medicine: int | None,
    timeout_seconds: float,
    step_delay_seconds: float,
):
    """Mantiene SPADE nel processo principale e Tk nel processo grafico."""

    from tamagotchi_wild.simulation import run_simulation

    context = get_context("spawn")
    frame_queue = context.Queue()
    result_queue = context.Queue()
    process = context.Process(
        target=_gui_worker,
        args=(
            frame_queue,
            result_queue,
            config,
            step_delay_seconds,
        ),
        name="cras-gui",
        daemon=True,
    )
    process.start()
    try:
        result = run_simulation(
            config,
            food,
            medicine,
            timeout_seconds,
            visualization_queue=frame_queue,
        )
        result_queue.put(result)
        process.join()
        if process.exitcode not in (0, None):
            raise RuntimeError(
                f"the graphical process stopped with exit code {process.exitcode}"
            )
        return result
    except Exception as exc:
        result_queue.put(exc)
        process.join()
        raise
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        frame_queue.cancel_join_thread()
        result_queue.cancel_join_thread()
        frame_queue.close()
        result_queue.close()


def _gui_worker(
    frame_queue,
    result_queue,
    config: SimulationConfig,
    step_delay_seconds: float,
) -> None:
    """Crea Tk nel main thread del processo dedicato alla finestra."""

    RescueCenterGUI(
        frame_queue,
        result_queue,
        config,
        step_delay_seconds,
    ).run()
