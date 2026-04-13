# Bundled soul templates — role archetypes for the agent fleet.
# Created: 2026-04-13 (Move 6 PR-A) — Arrow (sales), Flash (content),
# Cyborg (recruiting), Analyst (research). Each ships as a YAML file
# alongside this package so installations get them by default. Custom
# templates live elsewhere; SoulFactory.load_template() accepts any path.

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent

BUNDLED_TEMPLATES = ["arrow", "flash", "cyborg", "analyst"]


def template_path(name: str) -> Path:
    """Return the path to a bundled template by name."""
    return TEMPLATES_DIR / f"{name}.yaml"


def list_bundled() -> list[str]:
    """Return the names of bundled templates available on disk."""
    return [p.stem for p in TEMPLATES_DIR.glob("*.yaml")]


__all__ = ["BUNDLED_TEMPLATES", "TEMPLATES_DIR", "list_bundled", "template_path"]
