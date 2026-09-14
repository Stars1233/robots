"""A shipped driver that fails to import is reported at the default log level.

``_register_shipped_drivers`` guards each import so one broken SDK install
cannot cost the other drivers their registration. The guard used to log the
skip at ``DEBUG``, so under the default configuration the robot simply vanished
from ``list_native_drivers()`` and ``Robot(name, mode="real", driver="strands")``
refused with "No native driver is registered" -- naming every driver except the
one that broke, and never the ``ImportError`` that broke it.
"""

from __future__ import annotations

import importlib
import logging

import pytest

import strands_robots.drivers as drivers_mod

_BROKEN_MODULE, _BROKEN_CLASS, _ = drivers_mod._SHIPPED_DRIVERS[0]


@pytest.fixture
def one_shipped_driver_fails_to_import(monkeypatch: pytest.MonkeyPatch) -> str:
    """Make the first shipped driver's import raise; every other import is real."""
    real_import = importlib.import_module
    reason = "libunobtainium.so: cannot open shared object file"

    def failing_import(name: str, package: str | None = None):  # type: ignore[no-untyped-def]
        if name == _BROKEN_MODULE:
            raise ImportError(reason)
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", failing_import)
    return reason


def test_a_failed_shipped_driver_import_is_a_warning_naming_the_cause(
    one_shipped_driver_fails_to_import: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="strands_robots.drivers"):
        drivers_mod._register_shipped_drivers()

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and _BROKEN_MODULE in r.getMessage()]
    assert warnings, (
        f"no WARNING names {_BROKEN_MODULE}: {[r.getMessage() for r in caplog.records]}. "
        "A shipped driver that did not import vanishes from list_native_drivers() with "
        "nothing shown at the default log level."
    )
    message = warnings[0].getMessage()
    assert _BROKEN_CLASS in message
    assert "ImportError" in message
    assert one_shipped_driver_fails_to_import in message


def test_the_other_shipped_drivers_still_register(one_shipped_driver_fails_to_import: str) -> None:
    """The seam's guarantee is unchanged: one broken driver skips only itself."""
    drivers_mod._register_shipped_drivers()
    others = {m for m, _, _ in drivers_mod._SHIPPED_DRIVERS} - {_BROKEN_MODULE}
    assert others
    for module_path in others:
        importlib.import_module(module_path)
