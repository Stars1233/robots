"""A mixed observation routes its bare cameras; one ``observation.*`` key does not opt the whole dict out.

``_to_lerobot_observation`` documents a per-key rule: keys already starting
with ``observation.`` pass through, bare camera names bind to the declared
image features by exact name. The line under it returned the WHOLE dict
untouched as soon as ANY key carried the prefix, so
``{"top": frame, "observation.state": vector}`` never reached the camera
routing and lerobot raised a bare ``KeyError: 'observation.images.top'`` from
``predict_action_chunk``. These pin the per-key rule.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from strands_robots.policies.lerobot_local.policy import LerobotLocalPolicy


class _VisualFeature:
    """Minimal stand-in for a declared VISUAL ``PolicyFeature``."""

    class _T:
        name = "VISUAL"

    type = _T()


def _act_style_policy() -> LerobotLocalPolicy:
    """A policy declaring ``observation.images.top`` + ``observation.state``, ACT-style."""
    with patch.object(LerobotLocalPolicy, "_load_model"):
        p = LerobotLocalPolicy(pretrained_name_or_path="test/model")
    p._input_features = {
        "observation.images.top": _VisualFeature(),
        "observation.state": object(),
    }
    p.robot_state_keys = [f"joint_{i}" for i in range(14)]
    return p


def test_bare_camera_beside_a_composed_state_binds_by_name():
    """``top`` binds to ``observation.images.top`` although ``observation.state`` was supplied."""
    p = _act_style_policy()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    state = np.zeros(14, dtype=np.float32)

    out = p._to_lerobot_observation({"top": frame, "observation.state": state})

    assert "observation.images.top" in out, sorted(out)
    assert out["observation.images.top"] is frame
    assert out["observation.state"] is state
    assert "top" not in out


def test_a_supplied_image_feature_is_not_filled_twice():
    """A prefixed image key passes through and a bare extra camera does not displace it."""
    p = _act_style_policy()
    top = np.zeros((480, 640, 3), dtype=np.uint8)
    default = np.ones((480, 640, 3), dtype=np.uint8)
    scalars = {f"joint_{i}": 0.0 for i in range(14)}

    out = p._to_lerobot_observation({"observation.images.top": top, "default": default, **scalars})

    assert out["observation.images.top"] is top
    assert out["observation.state"].shape == (14,)
    assert p.positional_fallback_used is False


def test_a_fully_formatted_observation_still_passes_through_unchanged():
    p = _act_style_policy()
    obs = {
        "observation.images.top": np.zeros((480, 640, 3), dtype=np.uint8),
        "observation.state": np.zeros(14, dtype=np.float32),
        "task": "stack",
    }

    out = p._to_lerobot_observation(obs)

    assert out == obs
