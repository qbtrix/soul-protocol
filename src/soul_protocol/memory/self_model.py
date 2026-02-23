# memory/self_model.py — Klein's self-concept model for digital souls.
# Updated: 2026-02-23 — Emergent domain discovery replaces hardcoded domain matching.
#   Domains now grow organically from interaction content instead of being limited
#   to 6 predefined categories. DEFAULT_SEED_DOMAINS provides backward-compatible
#   bootstrapping. Domain keywords expand over time as the soul encounters new content.
#   Added STOP_WORDS filtering, dynamic domain creation, and seed_domains constructor param.

from __future__ import annotations

from soul_protocol.memory.search import tokenize
from soul_protocol.types import Interaction, MemoryEntry, SelfImage


# ---------------------------------------------------------------------------
# Stop words: common English words that don't contribute to domain identity.
# tokenize() already strips words < 3 chars, so we only need 3+ letter words.
# ---------------------------------------------------------------------------

STOP_WORDS: frozenset[str] = frozenset({
    # Articles & determiners
    "the", "this", "that", "these", "those", "which", "what",
    # Pronouns
    "you", "your", "yours", "yourself", "she", "her", "hers", "him", "his",
    "they", "them", "their", "theirs", "its", "who", "whom", "whose",
    # Common verbs & auxiliaries
    "are", "was", "were", "been", "being", "have", "has", "had", "having",
    "does", "did", "doing", "will", "would", "shall", "should", "may",
    "might", "must", "can", "could", "need",
    # Prepositions & conjunctions
    "for", "and", "nor", "but", "yet", "not", "with", "from", "into",
    "about", "than", "then", "also", "just", "more", "most", "very",
    "too", "some", "any", "all", "each", "every", "both", "few", "many",
    "much", "own", "other", "another", "same", "such", "only",
    "over", "under", "between", "through", "after", "before", "during",
    "above", "below", "out", "off", "down", "once", "here", "there",
    "when", "where", "why", "how", "while", "until",
    # Conversational filler
    "help", "please", "thanks", "thank", "sure", "okay", "yes", "yeah",
    "hey", "hello", "well", "like", "really", "think", "know",
    "want", "get", "got", "let", "see", "say", "said", "thing", "things",
    "way", "make", "made", "use", "used", "try", "give", "take",
    "come", "look", "going", "now", "new", "one", "two",
})


# ---------------------------------------------------------------------------
# Default seed domains: sensible bootstrapping keywords for common use cases.
# Renamed from DOMAIN_KEYWORDS — kept for backward compatibility and to give
# new souls a head start before they accumulate enough experience to discover
# their own domains.
# ---------------------------------------------------------------------------

DEFAULT_SEED_DOMAINS: dict[str, list[str]] = {
    "technical_helper": [
        "python", "javascript", "code", "programming", "debug", "error",
        "api", "database", "server", "deploy", "git", "docker",
        "algorithm", "function", "class", "variable", "testing",
        "fastapi", "django", "react", "typescript", "rust",
    ],
    "creative_writer": [
        "write", "story", "poem", "creative", "fiction", "narrative",
        "character", "plot", "blog", "essay", "article", "content",
        "copywriting", "draft", "edit", "prose",
    ],
    "knowledge_guide": [
        "explain", "teach", "learn", "understand", "concept", "theory",
        "research", "study", "science", "history", "philosophy",
        "education", "tutorial", "guide", "documentation",
    ],
    "problem_solver": [
        "solve", "fix", "issue", "problem", "solution",
        "troubleshoot", "diagnose", "analyze", "investigate",
        "debug", "resolve", "broken",
    ],
    "creative_collaborator": [
        "brainstorm", "idea", "design", "prototype", "sketch",
        "innovation", "experiment", "iterate", "collaborate",
        "vision", "concept", "create",
    ],
    "emotional_companion": [
        "feel", "emotion", "support", "listen", "care", "empathy",
        "comfort", "friend", "companion", "talk", "vent", "advice",
        "stress", "anxious", "happy", "sad",
    ],
}

# Backward-compatible alias
DOMAIN_KEYWORDS = DEFAULT_SEED_DOMAINS


class SelfModelManager:
    """Tracks the soul's evolving self-concept (Klein's self-model).

    The soul learns who it is by observing what it does. Over time, patterns
    emerge: "I help with code a lot → I am a technical helper."

    Domains are not hardcoded — they're discovered from experience. The soul
    starts with optional seed domains for bootstrapping, then creates new
    domains on the fly as it encounters content outside known categories.
    """

    def __init__(self, seed_domains: dict[str, list[str]] | None = None) -> None:
        self._self_images: dict[str, SelfImage] = {}
        self._relationship_notes: dict[str, str] = {}
        # Domain keywords are dynamic — they grow with experience
        self._domain_keywords: dict[str, set[str]] = {}

        # Load seed domains (defaults if none provided)
        source = seed_domains if seed_domains is not None else DEFAULT_SEED_DOMAINS
        for domain, keywords in source.items():
            self._domain_keywords[domain] = set(keywords)

    @property
    def self_images(self) -> dict[str, SelfImage]:
        """All self-images the soul has developed."""
        return dict(self._self_images)

    @property
    def relationship_notes(self) -> dict[str, str]:
        """What the soul knows about key people/entities."""
        return dict(self._relationship_notes)

    def update_from_interaction(
        self,
        interaction: Interaction,
        extracted_facts: list[MemoryEntry],
    ) -> None:
        """Update self-concept based on an observed interaction.

        Uses emergent domain discovery:
        1. Tokenize interaction content, filter stop words
        2. Score against existing domains (seed + learned)
        3. If a good match (>= 2 keyword overlaps), reinforce that domain
           and expand its vocabulary with new keywords
        4. If no good match but >= 2 meaningful keywords, create a new domain

        Args:
            interaction: The interaction that was observed.
            extracted_facts: Facts extracted from this interaction.
        """
        combined = f"{interaction.user_input} {interaction.agent_output}"
        tokens = tokenize(combined)

        # Also include tokens from extracted facts
        for fact in extracted_facts:
            tokens |= tokenize(fact.content)

        # Filter out stop words to get meaningful keywords
        meaningful = tokens - STOP_WORDS

        # Score against existing domains
        best_domain: str | None = None
        best_score = 0
        for domain, keywords in self._domain_keywords.items():
            score = len(meaningful & keywords)
            if score > best_score:
                best_score = score
                best_domain = domain

        if best_domain and best_score >= 2:
            # Good match — reinforce existing domain and expand its vocabulary
            self._update_domain(best_domain, best_score)
            self._domain_keywords[best_domain] |= meaningful
        elif len(meaningful) >= 2:
            # No good match — create a new domain from content
            domain_name = self._generate_domain_name(meaningful)
            self._domain_keywords[domain_name] = set(meaningful)
            self._update_domain(domain_name, len(meaningful))

        # Extract relationship notes from facts
        for fact in extracted_facts:
            content_lower = fact.content.lower()
            if "user's name is" in content_lower:
                name = fact.content.split("is")[-1].strip()
                self._relationship_notes["user"] = f"Name: {name}"
            elif "user works at" in content_lower:
                workplace = fact.content.split("at")[-1].strip()
                existing = self._relationship_notes.get("user", "")
                if "Works at" not in existing:
                    self._relationship_notes["user"] = (
                        f"{existing}; Works at: {workplace}" if existing else f"Works at: {workplace}"
                    )

    @staticmethod
    def _generate_domain_name(keywords: set[str]) -> str:
        """Generate a descriptive domain name from a set of meaningful keywords.

        Picks the 1-2 most distinctive keywords (longest words are more specific)
        and joins them with an underscore.

        Args:
            keywords: Set of meaningful (non-stop) tokens from the interaction.

        Returns:
            A snake_case domain name like "cooking_recipe" or "fitness".
        """
        # Sort by length descending (longer = more specific), then alphabetically for stability
        ranked = sorted(keywords, key=lambda w: (-len(w), w))
        if len(ranked) >= 2:
            return f"{ranked[0]}_{ranked[1]}"
        return ranked[0] if ranked else "general"

    def _update_domain(self, domain: str, match_count: int) -> None:
        """Increment evidence for a self-image domain.

        Confidence grows with evidence but has diminishing returns —
        the soul becomes more certain over time but never fully certain.

        Args:
            domain: The self-image domain (e.g., "technical_helper").
            match_count: How many keyword matches were found.
        """
        if domain not in self._self_images:
            self._self_images[domain] = SelfImage(
                domain=domain,
                confidence=0.1,
                evidence_count=0,
            )

        img = self._self_images[domain]
        img.evidence_count += match_count

        # Confidence formula: diminishing returns curve
        # Starts at 0.1, approaches 0.95 as evidence grows
        img.confidence = min(0.95, 0.1 + 0.85 * (1 - 1 / (1 + img.evidence_count * 0.1)))

    def get_active_self_images(self, limit: int = 3) -> list[SelfImage]:
        """Return the top self-images by confidence.

        Args:
            limit: Maximum number of self-images to return.

        Returns:
            List of SelfImage sorted by confidence descending.
        """
        images = sorted(
            self._self_images.values(),
            key=lambda img: (-img.confidence, -img.evidence_count),
        )
        return images[:limit]

    def to_dict(self) -> dict:
        """Serialize the self-model to a plain dict.

        Returns:
            Dict with self_images, relationship_notes, and domain_keywords.
        """
        return {
            "self_images": {
                domain: img.model_dump()
                for domain, img in self._self_images.items()
            },
            "relationship_notes": dict(self._relationship_notes),
            "domain_keywords": {
                domain: sorted(keywords)
                for domain, keywords in self._domain_keywords.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> SelfModelManager:
        """Deserialize a self-model from a plain dict.

        Args:
            data: Dict as produced by to_dict().

        Returns:
            A fully reconstituted SelfModelManager.
        """
        manager = cls()

        for domain, img_data in data.get("self_images", {}).items():
            manager._self_images[domain] = SelfImage.model_validate(img_data)

        manager._relationship_notes = dict(data.get("relationship_notes", {}))

        # Restore learned domain keywords (merges with defaults already loaded by __init__)
        for domain, keywords in data.get("domain_keywords", {}).items():
            manager._domain_keywords[domain] = set(keywords)

        return manager

    def to_prompt_fragment(self) -> str:
        """Generate a prompt fragment describing the soul's self-concept.

        Suitable for inclusion in system prompts.

        Returns:
            A human-readable string describing active self-images,
            or empty string if no self-images exist.
        """
        active = self.get_active_self_images(limit=3)
        if not active:
            return ""

        lines = ["## Self-Understanding", ""]
        for img in active:
            confidence_label = (
                "high" if img.confidence >= 0.7
                else "growing" if img.confidence >= 0.4
                else "emerging"
            )
            domain_display = img.domain.replace("_", " ")
            lines.append(
                f"- {domain_display} ({confidence_label} confidence, "
                f"{img.evidence_count} supporting interactions)"
            )

        return "\n".join(lines)
