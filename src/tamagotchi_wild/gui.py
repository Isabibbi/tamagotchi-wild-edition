
from __future__ import annotations

import logging

from nicegui import app, ui

from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.gui_bridge import SimulationBridge
from tamagotchi_wild.messaging import VisualizationUpdate
from tamagotchi_wild.visualization import (
    render_area_access,
    render_floorplan_svg,
    render_operator_roster,
    render_placeholder_svg,
    snapshot_metrics,
    timeline_entries,
)
from tamagotchi_wild.visualization.nicegui_theme import NICEGUI_CSS


logger = logging.getLogger(__name__)


class RescueCenterDashboard:

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
        self.previous_snapshot = None
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
                    "Connecting to SPADE…",
                    color="info",
                ).mark("simulation-status")
                self.pause_button = ui.button(
                    "Pause playback",
                    icon="pause",
                    on_click=self._toggle_playback,
                    color="slate-700",
                ).props("unelevated rounded")
                ui.button(
                    "Close",
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
                with ui.column().classes("lg:col-span-7 gap-5 min-w-0"):
                    self._build_floorplan_card()
                    self._build_staff_card()
                with ui.column().classes("lg:col-span-5 gap-5 min-w-0"):
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
                ui.label("Wildlife Rescue Centre").classes(
                    "text-2xl font-black text-slate-900"
                )
                ui.label(
                    "Feeding and medical care run together via SPADE/XMPP."
                ).classes("text-sm text-slate-500")
            with ui.row().classes("items-end gap-3"):
                ui.badge(
                    f"{self.config.operator_count} operators",
                    color="blue-700",
                ).props("outline")
                ui.badge(
                    (
                        "1 animal"
                        if self.config.animal_count == 1
                        else f"{self.config.animal_count} animals"
                    ),
                    color="green-700",
                ).props("outline")
                ui.select(
                    {
                        0.05: "Very fast",
                        0.10: "Fast",
                        0.20: "Normal",
                        0.50: "Slow",
                    },
                    label="Playback speed",
                    value=self.step_delay_seconds,
                    on_change=self._set_speed,
                ).props("outlined dense").classes("w-44")

    def _build_metrics(self) -> None:
        with ui.element("div").classes(
            "w-full grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
        ):
            self.healthy_value, self.healthy_progress = self._metric_card(
                "favorite",
                "Healthy animals",
                "0/0",
                "green",
            )
            self.bowls_value, self.bowls_progress = self._metric_card(
                "restaurant",
                "Full bowls",
                "0/0",
                "orange",
            )
            self.medical_value, self.medical_progress = self._metric_card(
                "medical_services",
                "Treatments done",
                "0/0",
                "blue",
            )
            self.resources_value, _ = self._metric_card(
                "inventory_2",
                "Available stock",
                "Food 0 · Medicine 0",
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
            if title != "Available stock":
                progress = ui.linear_progress(
                    0,
                    show_value=False,
                    color=f"{tone}-600",
                ).props("rounded")
            return value_label, progress

    def _build_floorplan_card(self) -> None:
        with ui.card().classes("cras-card w-full p-5 gap-4"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label("Rescue centre").classes(
                        "text-lg font-black text-slate-900"
                    )
                    ui.label(
                        "Illustrated floorplan with rooms, cages and operators in motion."
                    ).classes("text-xs text-slate-500")
                self.event_label = ui.label("Waiting for first snapshot").classes(
                    "text-xs font-bold text-green-700"
                )
            self.floorplan_html = ui.html(
                render_placeholder_svg(),
                sanitize=False,
            ).classes("floorplan-shell w-full").mark("cras-floorplan")

    def _build_staff_card(self) -> None:
        with ui.card().classes("cras-card w-full p-5 gap-4"):
            ui.label("Active staff").classes("text-lg font-black text-slate-900")
            ui.label(
                "Green = Free · Red = Busy · Gray = Waiting"
            ).classes("text-xs text-slate-500")
            self.staff_html = ui.html(
                '<div class="text-slate-400 text-sm">Waiting for agents…</div>',
                sanitize=False,
            ).classes("w-full").mark("staff-roster")

    def _build_timeline_card(self) -> None:
        with ui.card().classes("cras-card timeline-card w-full p-5 gap-4"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label("Live timeline").classes(
                        "text-lg font-black text-slate-900"
                    )
                    ui.label(
                        "Completed actions and blocked attempts, step by step"
                    ).classes("text-xs text-slate-500")
                ui.icon("sensors", color="green-600")
            self.timeline = ui.log(max_lines=600).classes(
                "event-log w-full p-3"
            ).mark("event-timeline")
            self.timeline.push(
                "Connecting to Visualization Agent SPADE…",
                classes="timeline-entry",
            )

    def _build_access_card(self) -> None:
        with ui.card().classes("cras-card w-full p-5 gap-4"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Area capacity").classes(
                    "text-lg font-black text-slate-900"
                )
                self.active_value = ui.badge("0 active", color="green-700")
            self.access_html = ui.html(
                '<div class="text-slate-400 text-sm">Waiting for state…</div>',
                sanitize=False,
            ).classes("w-full").mark("area-access")

    def _poll_updates(self) -> None:
        self.poll_count += 1
        if self.poll_count == 1:
            self.status_badge.set_text("Starting SPADE worker…")
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
        self.status_badge.set_text("SPADE connected")
        self.status_badge.props("color=positive")
        rejected = update.event.get("action") == "action_rejected"
        self.event_label.set_text(
            f"Blocked attempt #{update.sequence:03d}"
            if rejected
            else f"SPADE event #{update.sequence:03d}"
        )
        frame_interval = (
            self.timer.interval
            if self.timer is not None
            else self.step_delay_seconds
        )
        self.floorplan_html.set_content(
            render_floorplan_svg(
                update.snapshot,
                previous_snapshot=self.previous_snapshot,
                transition_seconds=frame_interval * 0.82,
            )
        )
        self.previous_snapshot = update.snapshot
        self.staff_html.set_content(render_operator_roster(update.snapshot))
        self.access_html.set_content(render_area_access(update.snapshot))
        self.active_value.set_text(f"{metrics.active_operators} active")
        self.healthy_value.set_text(
            f"{metrics.healthy_animals}/{metrics.animal_count}"
        )
        self.bowls_value.set_text(f"{metrics.filled_bowls}/{metrics.bowl_count}")
        self.medical_value.set_text(
            f"{metrics.completed_medical_tasks}/{metrics.medical_task_count}"
        )
        self.resources_value.set_text(
            f"Food {metrics.food_remaining} · Medicine {metrics.medicine_remaining}"
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
        for index, entry in enumerate(entries):
            css_class = "timeline-entry"
            if entry.lstrip().startswith("↳"):
                css_class += " text-slate-400"
            if (
                rejected and index == len(entries) - 1
            ) or "on hold" in entry:
                css_class += " timeline-warning"
            self.timeline.push(entry, classes=css_class)

    def _finish(self, result) -> None:
        self.bridge.result = result
        if isinstance(result, Exception):
            self.status_badge.set_text("Simulation stopped")
            self.status_badge.props("color=negative")
            self.timeline.push(
                f"ERROR · {result}",
                classes="timeline-entry text-red-300",
            )
            return
        outcome = "Completed" if result.success else "Failed"
        self.status_badge.set_text(f"Simulation {outcome.lower()}")
        self.status_badge.props("color=positive" if result.success else "color=negative")
        self.timeline.push(
            f"END · Feeding {result.completed_feeding_tasks}/"
            f"{result.feeding_task_count} · Medical "
            f"{result.completed_medical_tasks}/{result.medical_task_count}",
            classes=(
                "timeline-entry text-green-300"
                if result.success
                else "timeline-entry text-red-300"
            ),
        )

    def _toggle_playback(self) -> None:
        if self.timer.active:
            self.timer.deactivate()
            self.pause_button.set_text("Resume playback")
            self.pause_button.props("icon=play_arrow")
        else:
            self.timer.activate()
            self.pause_button.set_text("Pause playback")
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
            language="en",
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
