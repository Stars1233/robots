"""A failed mid-hold refresh surfaces the true held time instead of the requested duration.

Review feedback on #3857: the ``break`` on a failed refresh fell through to
an outcome that still reported ``held_s=duration_s`` with ``status="success"``,
so a move that drove for 2 s was indistinguishable from one that drove for 10 s.
The fix surfaces the failure as ``status="error"`` with the true elapsed hold.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from strands_robots.drivers import earthrover
from strands_robots.drivers.earthrover import EarthRoverDriver

TWIST = {"linear": 0.5, "angular": 0.0}
STOP = {"linear": 0.0, "angular": 0.0}


class _FakeClock:
    """``time`` stand-in: ``sleep`` advances ``monotonic``."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class _FailAfterN:
    """Session stub whose twist-refresh POST fails after *n* successes.

    The stop command (linear=0, angular=0) always succeeds so the teardown
    path is not conflated with the refresh-failure path under test.
    """

    def __init__(self, fail_after: int) -> None:
        self._fail_after = fail_after
        self._twist_count = 0
        self.posts: list[dict[str, Any]] = []

    def get(self, url: str, timeout: float = 0.0, **_: Any) -> Any:
        return types.SimpleNamespace(status_code=200, text="", json=lambda: {"battery": 90})

    def post(self, url: str, json: Any = None, timeout: float = 0.0, **_: Any) -> Any:
        cmd = json["command"]
        self.posts.append(cmd)
        is_stop = cmd.get("linear", 1) == 0.0 and cmd.get("angular", 1) == 0.0
        if not is_stop:
            self._twist_count += 1
            if self._twist_count > self._fail_after:
                return types.SimpleNamespace(status_code=500, text="SDK error", json=lambda: {})
        return types.SimpleNamespace(status_code=200, text="", json=lambda: {})

    def close(self) -> None:
        pass


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    fake = _FakeClock()
    monkeypatch.setattr(earthrover, "time", fake)
    return fake


@pytest.fixture
def fail_on_second_refresh(monkeypatch: pytest.MonkeyPatch) -> _FailAfterN:
    """The first POST (initial twist) succeeds; the second POST (first refresh) fails."""
    stub = _FailAfterN(fail_after=1)
    fake = types.ModuleType("requests")
    fake.Session = lambda: stub  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "requests", fake)
    return stub


def test_mid_hold_refresh_failure_reports_true_elapsed_time(
    fail_on_second_refresh: _FailAfterN, clock: _FakeClock
) -> None:
    """A refresh failure at ~0.2 s of a 10 s hold must report held_s < 10."""
    driver = EarthRoverDriver()
    assert driver.connect_eagerly() is None
    answer = driver.move(linear=0.5, duration_s=10.0)

    # The answer MUST be an error - the hold was cut short.
    assert answer["status"] == "error", (
        "A failed mid-hold refresh must surface as status='error', not silently report a completed hold"
    )

    outcome = answer["content"][-1]["json"]
    # The true hold should be much less than the requested 10 s.
    assert outcome["held_s"] < 10.0, (
        f"held_s should reflect the true elapsed time, not the requested duration; got {outcome['held_s']}"
    )
    # The stop should still have been sent (early but intentional).
    assert outcome["stopped"] is True
    # The last POST should be the stop command.
    assert fail_on_second_refresh.posts[-1] == STOP


def test_successful_hold_reports_true_elapsed_time(clock: _FakeClock, monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful 10 s hold reports held_s close to 10.0, not some other value."""

    class _OkSession:
        posts: list[dict[str, Any]] = []

        def get(self, url: str, **_: Any) -> Any:
            return types.SimpleNamespace(status_code=200, text="", json=lambda: {"battery": 90})

        def post(self, url: str, json: Any = None, **_: Any) -> Any:
            self.posts.append(json["command"])
            return types.SimpleNamespace(status_code=200, text="", json=lambda: {})

        def close(self) -> None:
            pass

    stub = _OkSession()
    fake = types.ModuleType("requests")
    fake.Session = lambda: stub  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "requests", fake)

    driver = EarthRoverDriver()
    assert driver.connect_eagerly() is None
    answer = driver.move(linear=0.5, duration_s=10.0)
    assert answer["status"] == "success"
    outcome = answer["content"][0]["json"]
    # The held_s should be approximately the requested duration (within rounding).
    assert outcome["held_s"] == pytest.approx(10.0, abs=0.01)
