# dna/prompt.py — Convert soul DNA into system prompts and markdown representations
# Updated: v0.2.0 — Self-model insights are now appended by Soul.to_system_prompt()
#   rather than being generated here. This module remains unchanged in its core API.

from __future__ import annotations

from soul_protocol.types import DNA, CoreMemory, Identity, SoulState


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
    lines.append(f"- **Energy regen rate:** {b.energy_regen_rate}")
    lines.append("")

    return "\n".join(lines)
