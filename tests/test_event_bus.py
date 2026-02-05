"""Tests for EventBus."""

import sys
import threading

sys.path.insert(0, ".")

from src.engine.event_bus import EventBus


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe("tick", lambda t, d: received.append((t, d)))
        bus.publish("tick", {"bid": 1.0})
        assert len(received) == 1
        assert received[0] == ("tick", {"bid": 1.0})

    def test_multiple_subscribers(self):
        bus = EventBus()
        results_a = []
        results_b = []
        bus.subscribe("tick", lambda t, d: results_a.append(d))
        bus.subscribe("tick", lambda t, d: results_b.append(d))
        bus.publish("tick", "hello")
        assert len(results_a) == 1
        assert len(results_b) == 1

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda t, d: received.append(d)
        bus.subscribe("tick", handler)
        bus.unsubscribe("tick", handler)
        bus.publish("tick", "data")
        assert len(received) == 0

    def test_unsubscribe_nonexistent_handler(self):
        bus = EventBus()
        # Should not raise
        bus.unsubscribe("tick", lambda t, d: None)

    def test_different_event_types(self):
        bus = EventBus()
        ticks = []
        signals = []
        bus.subscribe("tick", lambda t, d: ticks.append(d))
        bus.subscribe("signal", lambda t, d: signals.append(d))
        bus.publish("tick", "t1")
        bus.publish("signal", "s1")
        assert len(ticks) == 1
        assert len(signals) == 1

    def test_handler_exception_doesnt_crash(self):
        bus = EventBus()
        received = []

        def bad_handler(t, d):
            raise ValueError("boom")

        bus.subscribe("tick", bad_handler)
        bus.subscribe("tick", lambda t, d: received.append(d))
        # Should not raise, second handler still runs
        bus.publish("tick", "data")
        assert len(received) == 1
