"""测试 EventBus — 发布/订阅正确性"""

import pytest
from app.infrastructure.events import EventBus, DomainEvent, EventType


@pytest.mark.asyncio
async def test_memory_pub_sub():
    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event)

    await bus.subscribe("test:channel", handler)
    await bus.publish("test:channel", DomainEvent(
        type=EventType.PROGRESS,
        task_id="task-1",
        data={"phase": "coding"},
    ))

    assert len(received) == 1
    assert received[0].task_id == "task-1"
    assert received[0].data["phase"] == "coding"


@pytest.mark.asyncio
async def test_multiple_handlers():
    bus = EventBus()
    results = []

    async def h1(event):
        results.append(("h1", event.task_id))

    async def h2(event):
        results.append(("h2", event.task_id))

    await bus.subscribe("ch", h1)
    await bus.subscribe("ch", h2)
    await bus.publish("ch", DomainEvent(type=EventType.LOG, task_id="t"))

    assert len(results) == 2


@pytest.mark.asyncio
async def test_emit_progress():
    bus = EventBus()
    events = []

    async def handler(e):
        events.append(e)
    await bus.subscribe("task:t1:progress", handler)
    await bus.emit_progress("t1", "coding", 50, "compiling")

    assert len(events) == 1
    assert events[0].data["phase"] == "coding"
    assert events[0].data["value"] == 50
