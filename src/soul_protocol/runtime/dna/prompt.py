# dna/prompt.py — Convert soul DNA into system prompts and markdown representations
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Updated: v0.2.0 — Self-model insights are now appended by Soul.to_system_prompt()
#   rather than being generated here. This module remains unchanged in its core API.
# Updated: Added full Biorhythms display to system prompt and markdown.
#   System prompt shows compact summary; only non-default fields are listed.
#   Markdown shows all configurable biorhythm fields.

from __future__ import annotations

from soul_protocol.runtime.types import DNA, Biorhythms, CoreMemory, Identity, SoulState


_BIORHYTHM_DEFAULTS = Biorhythms()


def _biorhythms_summary(b: Biorhythms) -> str:
    """Build a compact biorhythms string showing only non-default values.

    Special cases:
    - energy_drain_rate == 0 AND social_drain_rate == 0 → "always-on (no drain)"
    - auto_regen disabled → noted explicitly
    - All defaults → returns empty string (section is omitted)
    """
    d = _BIORHYTHM_DEFAULTS
    parts: list[str] = []

    # Detect always-on mode
    no_energy_drain = b.energy_drain_rate == 0.0
    no_social_drain = b.social_drain_rate == 0.0
    always_on = no_energy_drain and no_social_drain

    if always_on:
        parts.append("Energy: always-on (no drain)")
    else:
        if b.energy_drain_rate != d.energy_drain_rate:
            parts.append(f"energy drain: {b.energy_drain_rate}/interaction")
        if b.social_drain_rate != d.social_drain_rate:
            parts.append(f"social drain: {b.social_drain_rate}/interaction")

    if b.chronotype != d.chronotype:
        parts.append(f"chronotype: {b.chronotype}")
    if b.social_battery != d.social_battery:
        parts.append(f"social battery: {b.social_battery:.0f}%")
    if b.energy_regen_rate != d.energy_regen_rate:
        parts.append(f"regen: {b.energy_regen_rate}/hr")
    if b.tired_threshold != d.tired_threshold:
        if b.tired_threshold == 0.0:
            parts.append("tired threshold: disabled")
        else:
            parts.append(f"tired threshold: {b.tired_threshold:.0f}%")
    if b.mood_inertia != d.mood_inertia:
        parts.append(f"mood inertia: {b.mood_inertia:.2f}")
    if b.mood_sensitivity != d.mood_sensitivity:
        parts.append(f"mood sensitivity: {b.mood_sensitivity:.2f}")
    if not b.auto_regen:
        parts.append("auto-regen: off")

    return " | ".join(parts)


def dna_to_system_prompt(
    identity: Identity,
    dna: DNA,
    core_memory: CoreMemory,
    state: SoulState,
) -> str:
    """Generate a system prompt from the soul's full context.

    Combines identity, personality traits (OCEAN), communication style,
    current mood/energy state, and core memory into a single prompt string
    suitable for passing to an LLM as its system message.

    Args:
        identity: The soul's identity (name, archetype, values, etc.).
        dna: The soul's personality blueprint.
        core_memory: Always-loaded persona and human memory.
        state: Current mood, energy, and focus.

    Returns:
        A multi-section system prompt string.
    """
    p = dna.personality
    c = dna.communication

    sections: list[str] = []

    # --- Identity ---
    sections.append(f"You are {identity.name}.")
    if identity.archetype:
        sections.append(f"Archetype: {identity.archetype}")
    if identity.origin_story:
        sections.append(f"Origin: {identity.origin_story}")
    if identity.prime_directive:
        sections.append(f"Prime directive: {identity.prime_directive}")

    # --- Core values ---
    if identity.core_values:
        values_str = ", ".join(identity.core_values)
        sections.append(f"Core values: {values_str}")

    # --- Personality traits (OCEAN) ---
    sections.append("")
    sections.append("## Personality")
    sections.append(
        f"Openness: {p.openness:.1f} | "
        f"Conscientiousness: {p.conscientiousness:.1f} | "
        f"Extraversion: {p.extraversion:.1f} | "
        f"Agreeableness: {p.agreeableness:.1f} | "
        f"Neuroticism: {p.neuroticism:.1f}"
    )

    # --- Communication style ---
    sections.append("")
    sections.append("## Communication Style")
    sections.append(
        f"Warmth: {c.warmth} | Verbosity: {c.verbosity} | "
        f"Humor: {c.humor_style} | Emoji: {c.emoji_usage}"
    )

    # --- Current state ---
    sections.append("")
    sections.append("## Current State")
    sections.append(
        f"Mood: {state.mood.value} | Energy: {state.energy:.0f}% | Focus: {state.focus}"
    )

    # --- Biorhythms (compact, non-default only) ---
    b = dna.biorhythms
    bio_line = _biorhythms_summary(b)
    if bio_line:
        sections.append("")
        sections.append("## Biorhythms")
        sections.append(bio_line)

    # --- Core memory ---
    if core_memory.persona:
        sections.append("")
        sections.append("## Persona Memory")
        sections.append(core_memory.persona)

    if core_memory.human:
        sections.append("")
        sections.append("## Human Memory")
        sections.append(core_memory.human)

    return "\n".join(sections)


def dna_to_markdown(identity: Identity, dna: DNA) -> str:
    """Generate a human-readable markdown representation of the soul's DNA.

    Useful for exporting, debugging, or displaying the soul's personality
    in documentation.

    Args:
        identity: The soul's identity.
        dna: The soul's personality blueprint.

    Returns:
        A markdown string describing the soul.
    """
    p = dna.personality
    c = dna.communication
    b = dna.biorhythms

    lines: list[str] = []

    lines.append(f"# {identity.name}")
    lines.append("")

    if identity.archetype:
        lines.append(f"**Archetype:** {identity.archetype}")
        lines.append("")

    if identity.origin_story:
        lines.append(f"**Origin:** {identity.origin_story}")
        lines.append("")

    if identity.core_values:
        lines.append("## Core Values")
        lines.append("")
        for value in identity.core_values:
            lines.append(f"- {value}")
        lines.append("")

    # Personality
    lines.append("## Personality (OCEAN)")
    lines.append("")
    lines.append("| Trait | Score |")
    lines.append("|-------|-------|")
    lines.append(f"| Openness | {p.openness:.2f} |")
    lines.append(f"| Conscientiousness | {p.conscientiousness:.2f} |")
    lines.append(f"| Extraversion | {p.extraversion:.2f} |")
    lines.append(f"| Agreeableness | {p.agreeableness:.2f} |")
    lines.append(f"| Neuroticism | {p.neuroticism:.2f} |")
    lines.append("")

    # Communication
    lines.append("## Communication Style")
    lines.append("")
    lines.append(f"- **Warmth:** {c.warmth}")
    lines.append(f"- **Verbosity:** {c.verbosity}")
    lines.append(f"- **Humor:** {c.humor_style}")
    lines.append(f"- **Emoji usage:** {c.emoji_usage}")
    lines.append("")

    # Biorhythms
    lines.append("## Biorhythms")
    lines.append("")
    lines.append(f"- **Chronotype:** {b.chronotype}")
    lines.append(f"- **Social battery:** {b.social_battery:.0f}%")
    lines.append(f"- **Energy regen rate:** {b.energy_regen_rate}/hr")
    lines.append(f"- **Energy drain rate:** {b.energy_drain_rate}/interaction")
    lines.append(f"- **Social drain rate:** {b.social_drain_rate}/interaction")
    lines.append(f"- **Tired threshold:** {b.tired_threshold:.0f}%")
    lines.append(f"- **Mood inertia:** {b.mood_inertia:.2f}")
    lines.append(f"- **Mood sensitivity:** {b.mood_sensitivity:.2f}")
    lines.append(f"- **Auto-regen:** {'yes' if b.auto_regen else 'no'}")
    lines.append("")

    return "\n".join(lines)
