"""Dashboard NiceGUI alimentata esclusivamente dal Visualization Agent SPADE."""

from __future__ import annotations

import logging

from nicegui import app, ui

from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.gui_bridge import SimulationBridge
from tamagotchi_wild.messaging import VisualizationUpdate
from tamagotchi_wild.visualization import (
    render_area_access,
    render_grid_svg,
    render_operator_roster,
    render_placeholder_svg,
    snapshot_metrics,
    timeline_entries,
)
from tamagotchi_wild.visualization.nicegui_theme import NICEGUI_CSS


logger = logging.getLogger(__name__)


class RescueCenterDashboard:
    """Una singola pagina browser con playback degli snapshot SPADE."""

    def __init__(
        self,
        bridge: SimulationBridge,
        config: SimulationConfig,
        step_delay_seconds: float,
    ) -> None:
        self.bridge = bridge
        self.config = config
        self.step_delay_seconds = max(0.05, step_delay_seconds)
        self.seen_activity_count = 0
        self.last_sequence = -1
        self.poll_count = 0
        self.frame_index = 0
        self.finished = False
        self.timer = None
        self._build()

    def _build(self) -> None:
        with ui.header().classes(
            "bg-slate-950 text-white border-b border-slate-800 px-5 py-3"
        ):
            with ui.row().classes("w-full items-center gap-4"):
                ui.icon("pets", size="2rem", color="green-400")
                with ui.column().classes("gap-0"):
                    ui.label("Tamagotchi Wild Edition").classes(
                        "text-xl font-black tracking-tight"
                    )
                    ui.label("Multi-Agent Care for Virtual Pets").classes(
                        "text-xs text-slate-400"
                    )
                ui.space()
                self.status_badge = ui.badge(
                    "Connessione a SPADE…",
                    color="info",
                ).mark("simulation-status")
                self.pause_button = ui.button(
                    "Pausa playback",
                    icon="pause",
                    on_click=self._toggle_playback,
                    color="slate-700",
                ).props("unelevated rounded")
                ui.button(
                    "Chiudi",
                    icon="close",
                    on_click=app.shutdown,
                    color="negative",
                ).props("unelevated rounded").mark("close-dashboard")

        with ui.column().classes("w-full gap-5"):
            self._build_intro()
            self._build_metrics()
            with ui.element("div").classes(
                "w-full grid grid-cols-1 lg:grid-cols-12 gap-5 items-start"
            ):
                with ui.column().classes("lg:col-span-8 gap-5 min-w-0"):
                    self._build_grid_card()
                    self._build_staff_card()
                with ui.column().classes("lg:col-span-4 gap-5 min-w-0"):
                    self._build_timeline_card()
                    self._build_access_card()

        self.timer = ui.timer(
            self.step_delay_seconds,
            self._poll_updates,
            immediate=True,
        )

    def _build_intro(self) -> None:
        with ui.row().classes("w-full items-center justify-between gap-4"):
            with ui.column().classes("gap-1"):
                ui.label("Centro di Recupero Animali Selvatici").classes(
                    "text-2xl font-black text-slate-900"
                )
                ui.label(
                    "Alimentazione e cure mediche avanzano insieme tramite SPADE/XMPP."
                ).classes("text-sm text-slate-500")
            with ui.row().classes("items-end gap-3"):
                ui.badge(
                    f"{self.config.operator_count} operatori",
                    color="blue-700",
                ).props("outline")
                ui.badge(
                    (
                        "1 animale"
                        if self.config.animal_count == 1
                        else f"{self.config.animal_count} animali"
                    ),
                    color="green-700",
                ).props("outline")
                ui.select(
                    {
                        0.05: "Molto veloce",
                        0.10: "Veloce",
                        0.20: "Normale",
                        0.50: "Lento",
                    },
                    label="Velocità playback",
                    value=self.step_delay_seconds,
                    on_change=self._set_speed,
                ).props("outlined dense").classes("w-44")

    def _build_metrics(self) -> None:
        with ui.element("div").classes(
            "w-full grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
        ):
            self.healthy_value, self.healthy_progress = self._metric_card(
                "favorite",
                "Animali sani",
                "0/0",
                "green",
            )
            self.bowls_value, self.bowls_progress = self._metric_card(
                "restaurant",
                "Ciotole piene",
                "0/0",
                "orange",
            )
            self.medical_value, self.medical_progress = self._metric_card(
                "medical_services",
                "Cure completate",
                "0/0",
                "blue",
            )
            self.resources_value, _ = self._metric_card(
                "inventory_2",
                "Scorte disponibili",
                "Cibo 0 · Medicine 0",
                "purple",
            )

    @staticmethod
    def _metric_card(icon: str, title: str, value: str, tone: str):
        with ui.card().classes("metric-card w-full p-4 gap-2"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.icon(icon, size="1.35rem", color=f"{tone}-600")
                ui.label(title).classes(
                    "text-xs font-bold uppercase tracking-wide text-slate-500"
                )
            value_label = ui.label(value).classes(
                "text-2xl font-black text-slate-900"
            )
            progress = None
            if title != "Scorte disponibili":
                progress = ui.linear_progress(
                    0,
                    show_value=False,
                    color=f"{tone}-600",
                ).props("rounded")
            return value_label, progress

    def _build_grid_card(self) -> None:
        with ui.card().classes("cras-card w-full p-5 gap-4"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label("Mappa operativa").classes(
                        "text-lg font-black text-slate-900"
                    )
                    ui.label(
                        "Ogni operatore mostra target e percorso A* con un colore univoco."
                    ).classes("text-xs text-slate-500")
                self.event_label = ui.label("Snapshot iniziale in arrivo").classes(
                    "text-xs font-bold text-green-700"
                )
            self.grid_html = ui.html(
                render_placeholder_svg(),
                sanitize=False,
            ).classes("grid-shell w-full").mark("cras-grid")

    def _build_staff_card(self) -> None:
        with ui.card().classes("cras-card w-full p-5 gap-4"):
            ui.label("Staff operativo").classes("text-lg font-black text-slate-900")
            ui.label(
                "Il colore laterale identifica percorso e target; il bordo giallo indica l'accesso operativo."
            ).classes("text-xs text-slate-500")
            self.staff_html = ui.html(
                '<div class="text-slate-400 text-sm">In attesa degli agenti…</div>',
                sanitize=False,
            ).classes("w-full").mark("staff-roster")

    def _build_timeline_card(self) -> None:
        with ui.card().classes("cras-card w-full p-5 gap-4"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label("Cronologia live").classes(
                        "text-lg font-black text-slate-900"
                    )
                    ui.label("Trigger, decisioni e azioni in ordine temporale").classes(
                        "text-xs text-slate-500"
                    )
                ui.icon("sensors", color="green-600")
            self.timeline = ui.log(max_lines=600).classes(
                "event-log w-full h-[650px] p-3"
            ).mark("event-timeline")
            self.timeline.push("Connessione al Visualization Agent SPADE…")

    def _build_access_card(self) -> None:
        with ui.card().classes("cras-card w-full p-5 gap-4"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Occupazione fisica delle aree").classes(
                    "text-lg font-black text-slate-900"
                )
                self.active_value = ui.badge("0 con target", color="green-700")
            self.access_html = ui.html(
                '<div class="text-slate-400 text-sm">In attesa dello stato…</div>',
                sanitize=False,
            ).classes("w-full").mark("area-access")

    def _poll_updates(self) -> None:
        self.poll_count += 1
        if self.poll_count == 1:
            self.status_badge.set_text("Worker SPADE in avvio…")
        try:
            self._poll_updates_once()
        except Exception as exc:
            logger.exception("NiceGUI playback failed")
            self._finish(exc)

    def _poll_updates_once(self) -> None:
        self.bridge.report_process_failure()
        update = self.bridge.frame_at(self.frame_index)
        if update is not None:
            self.frame_index += 1
            self._apply_update(update)

        result = self.bridge.terminal_result()
        if update is None and result is not None and not self.finished:
            self.finished = True
            self._finish(result)

    def _apply_update(self, update: VisualizationUpdate) -> None:
        if update.sequence < self.last_sequence:
            return
        self.last_sequence = update.sequence
        metrics = snapshot_metrics(update.snapshot)
        self.status_badge.set_text("SPADE connesso")
        self.status_badge.props("color=positive")
        self.event_label.set_text(f"Evento SPADE #{update.sequence:03d}")
        self.grid_html.set_content(render_grid_svg(update.snapshot))
        self.staff_html.set_content(render_operator_roster(update.snapshot))
        self.access_html.set_content(render_area_access(update.snapshot))
        self.active_value.set_text(f"{metrics.active_operators} con target")
        self.healthy_value.set_text(
            f"{metrics.healthy_animals}/{metrics.animal_count}"
        )
        self.bowls_value.set_text(f"{metrics.filled_bowls}/{metrics.bowl_count}")
        self.medical_value.set_text(
            f"{metrics.completed_medical_tasks}/{metrics.medical_task_count}"
        )
        self.resources_value.set_text(
            f"Cibo {metrics.food_remaining} · Medicine {metrics.medicine_remaining}"
        )
        self.healthy_progress.set_value(
            _ratio(metrics.healthy_animals, metrics.animal_count)
        )
        self.bowls_progress.set_value(
            _ratio(metrics.filled_bowls, metrics.bowl_count)
        )
        self.medical_progress.set_value(
            _ratio(metrics.completed_medical_tasks, metrics.medical_task_count)
        )
        entries, self.seen_activity_count = timeline_entries(
            update,
            self.seen_activity_count,
        )
        for entry in entries:
            css_class = "text-slate-400" if entry.lstrip().startswith("↳") else ""
            self.timeline.push(entry, classes=css_class)

    def _finish(self, result) -> None:
        self.bridge.result = result
        if isinstance(result, Exception):
            self.status_badge.set_text("Simulazione interrotta")
            self.status_badge.props("color=negative")
            self.timeline.push(f"ERRORE · {result}", classes="text-red-300")
            return
        outcome = "Completata" if result.success else "Fallita"
        self.status_badge.set_text(f"Simulazione {outcome.lower()}")
        self.status_badge.props("color=positive" if result.success else "color=negative")
        self.timeline.push(
            f"FINE · Feeding {result.completed_feeding_tasks}/"
            f"{result.feeding_task_count} · Medical "
            f"{result.completed_medical_tasks}/{result.medical_task_count}",
            classes="text-green-300" if result.success else "text-red-300",
        )

    def _toggle_playback(self) -> None:
        if self.timer.active:
            self.timer.deactivate()
            self.pause_button.set_text("Riprendi playback")
            self.pause_button.props("icon=play_arrow")
        else:
            self.timer.activate()
            self.pause_button.set_text("Pausa playback")
            self.pause_button.props("icon=pause")

    def _set_speed(self, event) -> None:
        self.timer.interval = max(0.05, float(event.value))


def run_graphical_simulation(
    config: SimulationConfig,
    food: int | None,
    medicine: int | None,
    timeout_seconds: float,
    step_delay_seconds: float,
    port: int = 8080,
    show_browser: bool = True,
):
    """Esegue NiceGUI come server principale e SPADE come processo autonomo."""

    bridge = SimulationBridge(
        config,
        food,
        medicine,
        timeout_seconds,
    )
    bridge.start()
    app.on_shutdown(bridge.stop)

    def dashboard() -> None:
        try:
            ui.colors(
                primary="#15803d",
                secondary="#2563eb",
                accent="#7c3aed",
                positive="#16a34a",
                negative="#dc2626",
            )
            ui.add_css(NICEGUI_CSS)
            RescueCenterDashboard(
                bridge,
                config,
                step_delay_seconds,
            )
        except Exception as exc:
            logger.exception("NiceGUI dashboard construction failed")
            ui.label(f"Dashboard error: {type(exc).__name__}: {exc}")

    try:
        ui.run(
            root=dashboard,
            host="127.0.0.1",
            port=port,
            title="Tamagotchi Wild Edition · SPADE",
            favicon="🐾",
            language="it",
            dark=False,
            show=show_browser,
            reload=False,
            show_welcome_message=False,
            uvicorn_logging_level="warning",
        )
        return bridge.result
    finally:
        bridge.stop()


def _ratio(value: int, total: int) -> float:
    return value / total if total else 0.0
