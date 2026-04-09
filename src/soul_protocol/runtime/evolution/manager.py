# evolution/manager.py — EvolutionManager for proposing, approving, and applying DNA mutations.
# Updated: Fixed pending mutations not persisting — moved from in-memory list to
#   EvolutionConfig.pending so mutations survive save/reload cycles.
# Updated: Wired check_triggers() to accept optional evaluation_triggers from
#   Evaluator.check_evolution_triggers() and propose mutations for high-performance
#   streaks. Previously was a no-op placeholder.
# Updated: Added structured logging for mutation proposals, approvals,
#   rejections, and applications.

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from soul_protocol.runtime.types import DNA, EvolutionConfig, EvolutionMode, Interaction, Mutation

logger = logging.getLogger(__name__)


def _get_nested_attr(obj: object, path: str) -> str:
    """Resolve a dot-separated attribute path and return its string value."""
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current[part]
        else:
            current = getattr(current, part)
    return str(current)


def _set_nested_attr(obj: object, path: str, value: str) -> None:
    """Set a value at a dot-separated attribute path.

    Attempts type coercion: if the existing value is a float, the new value
    is cast to float; if int, cast to int. Otherwise stored as-is.
    """
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        if isinstance(current, dict):
            current = current[part]
        else:
            current = getattr(current, part)

    final_key = parts[-1]
    existing = getattr(current, final_key) if hasattr(current, final_key) else None

    # Coerce to the original type when possible
    if isinstance(existing, float):
        coerced: object = float(value)
    elif isinstance(existing, int):
        coerced = int(value)
    else:
        coerced = value

    setattr(current, final_key, coerced)


class EvolutionManager:
    """Manages trait evolution proposals, approvals, and application to DNA.

    Supports three modes:
    - **disabled**: mutations raise ``ValueError``
    - **supervised**: mutations are created as pending (``approved=None``)
      until explicitly approved or rejected
    - **autonomous**: mutations are auto-approved on proposal
    """

    def __init__(self, config: EvolutionConfig) -> None:
        self._config = config

    @property
    def config(self) -> EvolutionConfig:
        """Return the evolution configuration."""
        return self._config

    @property
    def pending(self) -> list[Mutation]:
        """Return mutations awaiting approval."""
        return [m for m in self._config.pending if m.approved is None]

    @property
    def history(self) -> list[Mutation]:
        """Return all mutations that have been resolved (approved or rejected)."""
        return list(self._config.history)

    async def propose(self, dna: DNA, trait: str, new_value: str, reason: str) -> Mutation:
        """Propose a mutation to a DNA trait.

        Args:
            dna: The current DNA to read the old value from.
            trait: Dot-separated trait path (e.g. ``"communication.warmth"``).
            new_value: The proposed new value as a string.
            reason: Human-readable justification for the change.

        Returns:
            The created ``Mutation`` object.

        Raises:
            ValueError: If evolution is disabled or the trait is immutable.
        """
        if self._config.mode == EvolutionMode.DISABLED:
            raise ValueError("Evolution is disabled — mutations cannot be proposed.")

        # Check immutability: the top-level trait category must not be immutable
        top_level_trait = trait.split(".")[0]
        if top_level_trait in self._config.immutable_traits:
            raise ValueError(f"Trait '{trait}' falls under immutable category '{top_level_trait}'.")

        old_value = _get_nested_attr(dna, trait)

        mutation = Mutation(
            id=uuid.uuid4().hex[:12],
            trait=trait,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            proposed_at=datetime.now(),
        )

        if self._config.mode == EvolutionMode.AUTONOMOUS:
            mutation.approved = True
            mutation.approved_at = datetime.now()
            self._config.history.append(mutation)
            logger.info(
                "Mutation auto-approved (autonomous): trait=%s, %s -> %s",
                trait,
                old_value,
                new_value,
            )
        else:
            # supervised — stays pending
            self._config.pending.append(mutation)
            logger.info(
                "Mutation proposed (supervised): id=%s, trait=%s, %s -> %s",
                mutation.id,
                trait,
                old_value,
                new_value,
            )

        return mutation

    async def approve(self, mutation_id: str) -> bool:
        """Approve a pending mutation.

        Returns:
            ``True`` if the mutation was found and approved, ``False`` otherwise.
        """
        for mutation in self._config.pending:
            if mutation.id == mutation_id and mutation.approved is None:
                mutation.approved = True
                mutation.approved_at = datetime.now()
                self._config.pending.remove(mutation)
                self._config.history.append(mutation)
                logger.info("Mutation approved: id=%s, trait=%s", mutation_id, mutation.trait)
                return True
        return False

    async def reject(self, mutation_id: str) -> bool:
        """Reject a pending mutation.

        Returns:
            ``True`` if the mutation was found and rejected, ``False`` otherwise.
        """
        for mutation in self._config.pending:
            if mutation.id == mutation_id and mutation.approved is None:
                mutation.approved = False
                self._config.pending.remove(mutation)
                self._config.history.append(mutation)
                logger.info(
                    "Mutation rejected: id=%s, trait=%s",
                    mutation_id,
                    mutation.trait,
                )
                return True
        return False

    def apply(self, dna: DNA, mutation_id: str) -> DNA:
        """Apply an approved mutation to DNA, returning a new DNA instance.

        The original ``dna`` is not mutated — a deep copy is made first.

        Args:
            dna: The current DNA.
            mutation_id: ID of an approved mutation.

        Returns:
            A new ``DNA`` with the mutation applied.

        Raises:
            ValueError: If the mutation is not found or not approved.
        """
        mutation = self._find_approved(mutation_id)
        if mutation is None:
            raise ValueError(f"No approved mutation found with id '{mutation_id}'.")

        # Deep copy via model serialization round-trip
        new_dna = DNA.model_validate(dna.model_dump())
        _set_nested_attr(new_dna, mutation.trait, mutation.new_value)
        return new_dna

    async def check_triggers(
        self,
        dna: DNA,
        interaction: Interaction,
        evaluation_triggers: list[dict] | None = None,
    ) -> list[Mutation]:
        """Check for automatic evolution triggers from evaluation patterns.

        Args:
            dna: Current DNA state.
            interaction: The triggering interaction.
            evaluation_triggers: Optional triggers from Evaluator.check_evolution_triggers().

        Returns:
            List of proposed mutations (empty if no triggers fired).
        """
        mutations: list[Mutation] = []
        if not evaluation_triggers:
            return mutations

        for trigger in evaluation_triggers:
            if trigger.get("trigger") == "high_performance_streak":
                try:
                    mutation = await self.propose(
                        dna=dna,
                        trait="communication.warmth",
                        new_value="high",
                        reason=trigger["reason"],
                    )
                    mutations.append(mutation)
                except (ValueError, KeyError):
                    # Trait immutable or invalid — skip silently
                    pass
        return mutations

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_approved(self, mutation_id: str) -> Mutation | None:
        """Search history for an approved mutation by ID."""
        for mutation in self._config.history:
            if mutation.id == mutation_id and mutation.approved is True:
                return mutation
        return None
