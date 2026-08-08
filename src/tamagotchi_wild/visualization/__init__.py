"""Dati di visualizzazione separati dallo stato autorevole."""

from tamagotchi_wild.visualization.projection import (
    CellProjection,
    GridProjection,
    project_grid,
)
from tamagotchi_wild.visualization.timeline import (
    describe_activity,
    describe_environment_event,
    timeline_entries,
)
from tamagotchi_wild.visualization.nicegui_view import (
    DashboardMetrics,
    render_area_access,
    render_grid_svg,
    render_operator_roster,
    render_placeholder_svg,
    snapshot_metrics,
)

__all__ = [
    "CellProjection",
    "GridProjection",
    "project_grid",
    "describe_activity",
    "describe_environment_event",
    "timeline_entries",
    "DashboardMetrics",
    "render_area_access",
    "render_grid_svg",
    "render_operator_roster",
    "render_placeholder_svg",
    "snapshot_metrics",
]
