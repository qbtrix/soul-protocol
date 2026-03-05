# tests/test_cognitive/test_prompts.py — Tests for prompt template formatting
#   and JSON parsability.
# Created: v0.2.1

from __future__ import annotations

import json

from soul_protocol.cognitive.engine import _parse_json
from soul_protocol.cognitive.prompts import (
    ENTITY_EXTRACTION_PROMPT,
    FACT_EXTRACTION_PROMPT,
    REFLECT_PROMPT,
    SELF_REFLECTION_PROMPT,
    SENTIMENT_PROMPT,
    SIGNIFICANCE_PROMPT,
)


class TestPromptFormatting:
    """Each prompt should format without KeyError when given all required vars."""

    def test_sentiment_prompt_formats(self) -> None:
        result = SENTIMENT_PROMPT.format(text="I am happy today")
        assert "I am happy today" in result
        assert "[TASK:sentiment]" in result

    def test_significance_prompt_formats(self) -> None:
        result = SIGNIFICANCE_PROMPT.format(
            values="helpfulness, empathy",
            recent_summaries="- talked about code\n- discussed AI",
            user_input="I love building things",
            agent_output="That sounds fun!",
        )
        assert "helpfulness, empathy" in result
        assert "I love building things" in result
        assert "[TASK:significance]" in result

    def test_fact_extraction_prompt_formats(self) -> None:
        result = FACT_EXTRACTION_PROMPT.format(
            user_input="My name is Alice",
            agent_output="Nice to meet you, Alice!",
        )
        assert "My name is Alice" in result
        assert "[TASK:extract_facts]" in result

    def test_entity_extraction_prompt_formats(self) -> None:
        result = ENTITY_EXTRACTION_PROMPT.format(
            user_input="I use Python and React",
            agent_output="Great stack!",
        )
        assert "Python and React" in result
        assert "[TASK:extract_entities]" in result

    def test_self_reflection_prompt_formats(self) -> None:
        result = SELF_REFLECTION_PROMPT.format(
            soul_name="Aria",
            current_self_images="- technical_helper: confidence=0.7",
            recent_episodes="User: help me debug\nAgent: sure!",
        )
        assert "Aria" in result
        assert "technical_helper" in result
        assert "[TASK:self_reflection]" in result

    def test_reflect_prompt_formats(self) -> None:
        result = REFLECT_PROMPT.format(
            soul_name="Aria",
            count=5,
            episodes="- episode 1\n- episode 2",
            self_model='{"self_images": {}}',
        )
        assert "Aria" in result
        assert "5" in result
        assert "[TASK:reflect]" in result


class TestPromptJsonExamples:
    """Typical LLM responses for each prompt should be parseable by _parse_json."""

    def test_sentiment_response(self) -> None:
        response = '{"valence": 0.7, "arousal": 0.5, "label": "joy"}'
        data = _parse_json(response)
        assert data["valence"] == 0.7

    def test_significance_response(self) -> None:
        response = (
            '{"novelty": 0.8, "emotional_intensity": 0.6, '
            '"goal_relevance": 0.4, "reasoning": "novel topic"}'
        )
        data = _parse_json(response)
        assert data["novelty"] == 0.8

    def test_fact_extraction_response(self) -> None:
        response = '[{"content": "User is a developer", "importance": 7}]'
        data = _parse_json(response)
        assert isinstance(data, list)
        assert data[0]["content"] == "User is a developer"

    def test_entity_extraction_response(self) -> None:
        response = '[{"name": "Python", "type": "technology", "relation": "uses"}]'
        data = _parse_json(response)
        assert isinstance(data, list)
        assert data[0]["name"] == "Python"

    def test_reflect_response(self) -> None:
        response = json.dumps(
            {
                "themes": ["coding", "AI"],
                "summaries": [
                    {"theme": "coding", "summary": "helped with Python", "importance": 7}
                ],
                "promote": ["ep_001"],
                "emotional_patterns": "generally positive",
                "self_insight": "I am a coding helper",
            }
        )
        data = _parse_json(response)
        assert "coding" in data["themes"]

    def test_fenced_sentiment_response(self) -> None:
        response = (
            "Here's my analysis:\n"
            "```json\n"
            '{"valence": -0.5, "arousal": 0.8, "label": "frustration"}\n'
            "```"
        )
        data = _parse_json(response)
        assert data["label"] == "frustration"

    def test_preamble_fact_response(self) -> None:
        response = (
            'I found the following facts:\n\n[{"content": "User lives in NYC", "importance": 7}]'
        )
        data = _parse_json(response)
        assert isinstance(data, list)
        assert data[0]["content"] == "User lives in NYC"
