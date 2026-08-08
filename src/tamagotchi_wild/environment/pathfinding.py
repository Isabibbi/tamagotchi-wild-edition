"""Pianificazione A* deterministica sulla griglia del CRAS."""

from __future__ import annotations

from heapq import heappop, heappush
from typing import Iterable

from tamagotchi_wild.domain import Position


def astar_path(
    start: Position,
    target: Position,
    width: int,
    height: int,
    blocked: Iterable[Position] = (),
) -> tuple[Position, ...] | None:
    """Restituisce le celle dopo ``start`` fino al target, oppure ``None``."""

    if start == target:
        return ()
    blocked_cells = set(blocked)
    blocked_cells.discard(start)
    if target in blocked_cells:
        return None

    frontier: list[tuple[int, int, int, int, Position]] = []
    heappush(frontier, (_manhattan(start, target), 0, start.y, start.x, start))
    came_from: dict[Position, Position] = {}
    cost_so_far = {start: 0}

    while frontier:
        _, current_cost, _, _, current = heappop(frontier)
        if current == target:
            return _reconstruct_path(came_from, start, target)
        if current_cost != cost_so_far[current]:
            continue

        for neighbour in _neighbours(current, width, height, target):
            if neighbour in blocked_cells:
                continue
            new_cost = current_cost + 1
            if new_cost >= cost_so_far.get(neighbour, width * height + 1):
                continue
            cost_so_far[neighbour] = new_cost
            came_from[neighbour] = current
            priority = new_cost + _manhattan(neighbour, target)
            heappush(
                frontier,
                (priority, new_cost, neighbour.y, neighbour.x, neighbour),
            )
    return None


def _neighbours(
    position: Position,
    width: int,
    height: int,
    target: Position,
) -> tuple[Position, ...]:
    candidates = (
        Position(position.x - 1, position.y),
        Position(position.x + 1, position.y),
        Position(position.x, position.y - 1),
        Position(position.x, position.y + 1),
    )
    valid = (
        item
        for item in candidates
        if 0 <= item.x < width and 0 <= item.y < height
    )
    return tuple(sorted(valid, key=lambda item: (_manhattan(item, target), item.y, item.x)))


def _reconstruct_path(
    came_from: dict[Position, Position],
    start: Position,
    target: Position,
) -> tuple[Position, ...]:
    path = [target]
    current = target
    while current != start:
        current = came_from[current]
        if current != start:
            path.append(current)
    path.reverse()
    return tuple(path)


def _manhattan(first: Position, second: Position) -> int:
    return abs(first.x - second.x) + abs(first.y - second.y)
