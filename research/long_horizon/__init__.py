# long_horizon/__init__.py — Long-horizon ablation study package.
# Created: 2026-03-11
# Proves the psychology stack matters at scale (100+ turn conversations).

from .analyze import LongHorizonAnalyzer
from .runner import LongHorizonRunner
from .scenarios import (
    LongHorizonScenario,
    TestPoint,
    generate_adversarial_burial,
    generate_emotional_rollercoaster,
    generate_life_updates,
)

__all__ = [
    "LongHorizonAnalyzer",
    "LongHorizonRunner",
    "LongHorizonScenario",
    "TestPoint",
    "generate_adversarial_burial",
    "generate_emotional_rollercoaster",
    "generate_life_updates",
]
