# runtime/templates.py — SoulFactory for creating souls from templates and batch spawning.
# Updated: feat/memory-visibility-templates — Full implementation of from_template()
#   and batch_spawn(). from_template() creates one soul from a SoulTemplate with
#   optional overrides. batch_spawn() creates N souls with controlled personality
#   variance. Each spawned soul gets a unique DID and slightly varied OCEAN traits.
# Updated: 2026-04-13 (Move 6 PR-A) — load_template() reads YAML/JSON files
#   so bundled templates (Arrow, Flash, Cyborg, Analyst) and custom user
#   templates can be loaded without hand-constructing the model.
# Updated: 2026-04-14 (v0.3.1 rebase) — from_template + batch_spawn now
#   propagate template.metadata["default_scope"] into seeded core memories
#   so Move 5 scope tags (see spec/scope.py) apply out of the box.

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

from soul_protocol.spec.template import SoulTemplate

logger = logging.getLogger(__name__)


class SoulFactory:
    """Factory for creating souls from templates.

    Provides two static methods:
    - from_template(): Create a single soul from a template with optional overrides.
    - batch_spawn(): Create N souls with slight personality variance.

    Also supports template registration for reuse.
    """

    def __init__(self) -> None:
        self._templates: dict[str, SoulTemplate] = {}

    def register(self, template: SoulTemplate) -> None:
        """Register a template for later use."""
        self._templates[template.name] = template

    def list_templates(self) -> list[str]:
        """List registered template names."""
        return list(self._templates.keys())

    def get(self, name: str) -> SoulTemplate | None:
        """Return a registered template by name (None if missing)."""
        return self._templates.get(name)

    @staticmethod
    def load_template(path: str | Path) -> SoulTemplate:
        """Load a SoulTemplate from a YAML or JSON file.

        File extension picks the parser: ``.yaml``/``.yml`` use PyYAML,
        anything else is parsed as JSON. Missing files raise FileNotFoundError;
        malformed payloads raise pydantic ValidationError so callers see the
        offending field clearly.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Template file not found: {path}")

        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml
            except ImportError as exc:
                raise ImportError(
                    "PyYAML is required to load YAML templates. "
                    "Install with `pip install soul-protocol[engine]`."
                ) from exc
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(text)

        return SoulTemplate.model_validate(data)

    @classmethod
    def load_bundled(cls, name: str) -> SoulTemplate:
        """Load one of the bundled role templates by short name (e.g. 'arrow')."""
        from soul_protocol.templates import template_path

        return cls.load_template(template_path(name))

    @staticmethod
    async def from_template(
        template: SoulTemplate,
        name: str | None = None,
        **overrides: Any,
    ) -> Any:
        """Create a single soul from a template.

        Args:
            template: The SoulTemplate blueprint to use.
            name: Override the template name. If None, uses template.name.
            **overrides: Additional keyword args passed to Soul.birth().
                Overrides take precedence over template values.

        Returns:
            A newly birthed Soul configured from the template.
        """
        # Lazy import to avoid circular dependency (soul -> templates -> soul)
        from soul_protocol.runtime.soul import Soul

        soul_name = name or template.name
        ocean = dict(template.personality) if template.personality else None

        # Merge template values with overrides (overrides win)
        birth_kwargs: dict[str, Any] = {
            "name": soul_name,
            "archetype": template.archetype,
        }
        if ocean:
            birth_kwargs["ocean"] = ocean

        # Apply overrides
        birth_kwargs.update(overrides)

        soul = await Soul.birth(**birth_kwargs)

        # Propagate default_scope from template metadata (Move 5 hand-off).
        # When the template declares ``default_scope``, every seeded core
        # memory inherits those hierarchical scope tags so RBAC/ABAC recall
        # filtering works on a freshly-instantiated soul without extra wiring.
        default_scope = template.metadata.get("default_scope")
        if isinstance(default_scope, str):
            default_scope = [default_scope]
        elif not isinstance(default_scope, list):
            default_scope = None

        # Set core memories from template
        for memory_text in template.core_memories:
            await soul.remember(memory_text, importance=9, scope=default_scope)

        # Register skills from template
        if template.skills:
            from soul_protocol.runtime.skills import Skill

            for skill_name in template.skills:
                skill_id = skill_name.lower().replace(" ", "_")
                skill = Skill(id=skill_id, name=skill_name)
                soul.skills.add(skill)

        logger.info(
            "Soul created from template: name=%s, template=%s",
            soul_name,
            template.name,
        )
        return soul

    @staticmethod
    async def batch_spawn(
        template: SoulTemplate,
        count: int,
        *,
        name_pattern: str = "{prefix}{index:03d}",
        rng_seed: int | None = None,
    ) -> list[Any]:
        """Create N souls from a template with controlled personality variance.

        Each spawned soul gets:
        - A unique name based on name_pattern
        - A unique DID
        - Slightly varied OCEAN traits (within +/- personality_variance)

        Args:
            template: The SoulTemplate blueprint.
            count: Number of souls to create.
            name_pattern: Format string for names. Available placeholders:
                {prefix} = template.name_prefix or template.name
                {index} = 1-based integer
                {name} = template.name
            rng_seed: Optional seed for reproducible variance.

        Returns:
            List of newly birthed Soul instances.
        """
        # Lazy import to avoid circular dependency
        from soul_protocol.runtime.skills import Skill
        from soul_protocol.runtime.soul import Soul

        rng = random.Random(rng_seed)
        prefix = template.name_prefix or template.name

        # Propagate default_scope so every spawned soul's core memories
        # carry the template's RBAC/ABAC tags (e.g. org:sales:*).
        default_scope = template.metadata.get("default_scope")
        if isinstance(default_scope, str):
            default_scope = [default_scope]
        elif not isinstance(default_scope, list):
            default_scope = None
        base_ocean = {
            "openness": template.personality.get("openness", 0.5),
            "conscientiousness": template.personality.get("conscientiousness", 0.5),
            "extraversion": template.personality.get("extraversion", 0.5),
            "agreeableness": template.personality.get("agreeableness", 0.5),
            "neuroticism": template.personality.get("neuroticism", 0.5),
        }

        souls: list[Any] = []
        for i in range(1, count + 1):
            # Generate varied OCEAN traits
            varied_ocean = {}
            for trait, base_val in base_ocean.items():
                variance = template.personality_variance
                delta = rng.uniform(-variance, variance)
                varied_ocean[trait] = max(0.0, min(1.0, base_val + delta))

            soul_name = name_pattern.format(
                prefix=prefix, index=i, name=template.name,
            )

            soul = await Soul.birth(
                name=soul_name,
                archetype=template.archetype,
                ocean=varied_ocean,
            )

            # Set core memories from template
            for memory_text in template.core_memories:
                await soul.remember(memory_text, importance=9, scope=default_scope)

            # Register skills from template
            for skill_name in template.skills:
                skill_id = skill_name.lower().replace(" ", "_")
                skill = Skill(id=skill_id, name=skill_name)
                soul.skills.add(skill)

            souls.append(soul)

        logger.info(
            "Batch spawned %d souls from template: template=%s, prefix=%s",
            count,
            template.name,
            prefix,
        )
        return souls
