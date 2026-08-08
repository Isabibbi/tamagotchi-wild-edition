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

__all__ = [
    "CellProjection",
    "GridProjection",
    "project_grid",
    "describe_activity",
    "describe_environment_event",
    "timeline_entries",
]
