# cognitive/prompts.py — Prompt templates for LLM-powered cognitive tasks.
# Created: v0.2.1 — Each template includes a [TASK:xxx] marker for routing
#   and a clear JSON output schema. Used by CognitiveProcessor to construct
#   prompts for the CognitiveEngine.

from __future__ import annotations

SENTIMENT_PROMPT = """[TASK:sentiment]
Analyze the emotional tone of this text.

Text: {text}

Return JSON:
{{"valence": <-1.0 to 1.0>, "arousal": <0.0 to 1.0>, "label": "<emotion>"}}

Labels: joy, gratitude, curiosity, frustration, confusion, sadness, excitement, neutral"""

SIGNIFICANCE_PROMPT = """[TASK:significance]
You are evaluating whether this interaction is worth remembering long-term \
for an AI companion.

Soul's core values: {values}
Recent interactions (for novelty):
{recent_summaries}

Current interaction:
  User: {user_input}
  Agent: {agent_output}

Rate each dimension 0.0 to 1.0:
Return JSON:
{{"novelty": <float>, "emotional_intensity": <float>, "goal_relevance": <float>, \
"reasoning": "<why>"}}"""

FACT_EXTRACTION_PROMPT = """[TASK:extract_facts]
Extract important facts about the user from this conversation.

Conversation:
  User: {user_input}
  Agent: {agent_output}

Return JSON array of facts:
[{{"content": "<fact statement>", "importance": <1-10>}}]

Only include facts that would be useful to remember long-term.
Return [] if no notable facts."""

ENTITY_EXTRACTION_PROMPT = """[TASK:extract_entities]
Extract named entities and the relations between them from this conversation.

Use this typed ontology for ``type`` (one of):
  person, place, org, concept, tool, document, event, relation
Custom types (e.g. ``pr``, ``channel``, ``library``) are accepted when none
of the built-ins fits — pass them as plain strings.

For each entity, list any directed relations to other entities mentioned
in the same conversation. Built-in relation predicates:
  mentions, related, depends_on, contributes_to, causes, follows,
  supersedes, owned_by

Conversation:
  User: {user_input}
  Agent: {agent_output}

Return a JSON array (and only a JSON array, no prose):
[
  {{
    "name": "<entity name>",
    "type": "<typed-ontology kind>",
    "relation": "<first-person relation to user, optional>",
    "relations": [
      {{"target": "<other entity>", "relation": "<predicate>", "weight": 0.0-1.0}}
    ]
  }}
]

Guidance:
- Skip pronouns (I, you, we) and generic words (the project, the team).
- Compound names like "Soul Protocol" stay as one entity, not two.
- ``weight`` is your confidence the relation is real (0.0-1.0). Drop the
  field if you have no signal.
- Return ``[]`` if no entities are present. Never return prose."""

SELF_REFLECTION_PROMPT = """[TASK:self_reflection]
You are {soul_name}. Review your recent interactions and reflect \
on who you are becoming.

Current self-understanding:
{current_self_images}

Recent interactions:
{recent_episodes}

Reflect on:
1. What domains do you help with most? (technical, creative, emotional, knowledge)
2. How confident are you in each identity facet?
3. Any new patterns emerging?

Return JSON:
{{
  "self_images": [{{"domain": "<str>", "confidence": <0-1>, "reasoning": "<why>"}}],
  "insights": "<freeform reflection>",
  "relationship_notes": {{"<entity>": "<what you know about them>"}}
}}"""

REFLECT_PROMPT = """[TASK:reflect]
You are {soul_name}. Review the last {count} interactions and consolidate \
your memories.

Episodes:
{episodes}

Current self-model:
{self_model}

Tasks:
1. Identify themes across these episodes
2. Which episodes can be compressed into summaries?
3. What should be promoted to long-term memory?
4. Any emotional patterns worth noting?

Return JSON:
{{
  "themes": ["<theme>"],
  "summaries": [{{"theme": "<str>", "summary": "<str>", "importance": <1-10>}}],
  "promote": ["<episode_id>"],
  "emotional_patterns": "<observation>",
  "self_insight": "<what you learned about yourself>"
}}"""
