"""Docs hygiene: every ``Robot(...)`` in ``docs/robots/bimanual.md`` constructs.

The page's one fence is a reader's first ``Robot()`` call for a two-arm rig, so
each line must be constructible on a clean install or say what stands in the
way. The registry is the oracle:

* a sim line (no ``mode="real"``) must name an entry with an ``asset`` block -
  ``bi_openarm`` declares hardware only, so ``Robot("bi_openarm")`` refused
  with "registered for real hardware only";
* an asset with ``auto_download: false`` is never fetched, so the fence must
  name the ``<dir>/<model_xml>`` the reader places by hand - ``trossen_wxai``
  was listed as a plain sim line and refused with "model file is not on disk";
* a ``mode="real"`` line must name an entry with a ``hardware`` block.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGE = REPO_ROOT / "docs" / "robots" / "bimanual.md"
ROBOTS_JSON = REPO_ROOT / "strands_robots" / "registry" / "robots.json"

_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _registry() -> dict[str, dict]:
    data = json.loads(ROBOTS_JSON.read_text())
    return data.get("robots", data)


def _robot_calls() -> list[tuple[str, dict[str, ast.expr], str]]:
    """Every ``Robot("<name>", ...)`` call as (name, keywords, fence source)."""
    calls: list[tuple[str, dict[str, ast.expr], str]] = []
    for fence in _FENCE_RE.findall(PAGE.read_text()):
        for node in ast.walk(ast.parse(fence)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Robot"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                calls.append((node.args[0].value, {k.arg: k.value for k in node.keywords if k.arg}, fence))
    return calls


def _is_real(keywords: dict[str, ast.expr]) -> bool:
    mode = keywords.get("mode")
    return isinstance(mode, ast.Constant) and mode.value == "real"


def test_the_fence_names_at_least_one_sim_and_one_hardware_rig() -> None:
    calls = _robot_calls()
    assert any(not _is_real(kw) for _, kw, _ in calls)
    assert any(_is_real(kw) for _, kw, _ in calls)


@pytest.mark.parametrize(("name", "keywords", "fence"), _robot_calls(), ids=lambda v: v if isinstance(v, str) else "")
def test_every_robot_call_names_a_route_the_registry_ships(
    name: str, keywords: dict[str, ast.expr], fence: str
) -> None:
    entry = _registry()[name]
    if _is_real(keywords):
        assert "hardware" in entry, f"Robot({name!r}, mode='real') names an entry with no hardware route"
        return
    asset = entry.get("asset")
    assert asset, f"Robot({name!r}) is written as a sim line but the entry declares no asset (hardware only)"
    if asset.get("auto_download", True) is False:
        placement = f"{asset['dir']}/{asset['model_xml']}"
        assert placement in fence, (
            f"Robot({name!r}) has auto_download=false, so the fence must tell the reader to place {placement}"
        )
