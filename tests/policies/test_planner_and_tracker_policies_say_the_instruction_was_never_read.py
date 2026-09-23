# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Providers that document ``instruction`` as ignored declare it to the envelopes.

``MoveIt2Policy``, ``ProtoMotionsPolicy`` and ``MicroduckPolicy`` all document
``instruction`` as ignored - the planner reads a kwargs goal, the tracker
follows a loaded motion, the gait follows a velocity command - but each left
``Policy.reads_instruction`` at its ``True`` default. ``run_policy(...,
instruction="pick up the red cube")`` therefore echoed the words with no
"does not read the instruction" notice, the misread the mock's envelope had
before it declared ``False``.
"""

from __future__ import annotations

import pytest

from strands_robots.policies.base import Policy, instruction_not_read_notice, provider_policy_class
from strands_robots.policies.microduck.policy import MicroduckPolicy
from strands_robots.policies.moveit2.policy import MoveIt2Policy
from strands_robots.policies.protomotions.policy import ProtoMotionsPolicy

_PROVIDERS = [
    pytest.param(
        "moveit2", MoveIt2Policy, "the planned trajectory to the target_pose or target_joints goal", id="moveit2"
    ),
    pytest.param("protomotions", ProtoMotionsPolicy, "the loaded motion's tracked joint targets", id="protomotions"),
    pytest.param("microduck", MicroduckPolicy, "the gait commanded by the velocity inputs", id="microduck"),
]


@pytest.mark.parametrize(("provider", "cls", "actions"), _PROVIDERS)
class TestTheContract:
    def test_the_class_declares_it_never_reads_the_instruction(
        self, provider: str, cls: type[Policy], actions: str
    ) -> None:
        assert cls.reads_instruction is False

    def test_the_notice_names_the_policy_and_its_actions(self, provider: str, cls: type[Policy], actions: str) -> None:
        notice = instruction_not_read_notice(cls)
        assert notice is not None, f"{cls.__name__} inherits reads_instruction=True; the envelope echoes the words"
        assert notice.startswith(f"Note: {cls.__name__} does not read the instruction.")
        assert f"Its actions - {actions} - were commanded" in notice

    def test_the_registry_answers_before_the_policy_is_built(
        self, provider: str, cls: type[Policy], actions: str
    ) -> None:
        # ``start`` reports before the executor thread constructs the policy,
        # so the class reached through the provider name is what it consults.
        assert provider_policy_class(provider) is cls
        assert instruction_not_read_notice(cls, pending=True) is not None
