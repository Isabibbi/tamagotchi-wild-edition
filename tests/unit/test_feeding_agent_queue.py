import asyncio

from tamagotchi_wild.agents.feeding_agent import FeedingAgent
from tamagotchi_wild.observability import ActivityLog


def test_feeding_agent_starts_only_one_task_at_a_time() -> None:
    agent = object.__new__(FeedingAgent)
    agent.feeding_lock = asyncio.Lock()
    agent.active_feeding_task = None
    agent.activity_log = ActivityLog()
    agent.agent_label = "feeding_01"

    async def exercise_queue() -> None:
        await agent._begin_feeding_task("feeding_001")
        second = asyncio.create_task(agent._begin_feeding_task("feeding_002"))
        await asyncio.sleep(0)

        assert agent.active_feeding_task == "feeding_001"
        assert second.done() is False

        agent._finish_feeding_task("feeding_001")
        await second

        assert agent.active_feeding_task == "feeding_002"
        agent._finish_feeding_task("feeding_002")

    asyncio.run(exercise_queue())

    assert agent.feeding_lock.locked() is False
    assert agent.activity_log.lines == (
        "task=feeding_002 agent=feeding_01 event=feeding_task_waiting",
    )
