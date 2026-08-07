"""Agenti SPADE e adattatori verso il dominio."""

from tamagotchi_wild.agents.environment_agent import (
    EnvironmentAgent,
    process_action_request,
)
from tamagotchi_wild.agents.feeding_agent import FeedingAgent
from tamagotchi_wild.agents.logistics_agent import LogisticsAgent

__all__ = [
    "EnvironmentAgent",
    "FeedingAgent",
    "LogisticsAgent",
    "process_action_request",
]
