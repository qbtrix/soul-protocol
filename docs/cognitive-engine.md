<!-- Covers: CognitiveEngine protocol, LLM integration examples (Claude, OpenAI,
     Ollama, Gemini), the 6 cognitive tasks and their prompt templates,
     fallback chain, SearchStrategy protocol, HeuristicEngine internals,
     and CognitiveProcessor orchestration. -->

# CognitiveEngine Guide

Soul Protocol works without an LLM. Every cognitive task has a built-in heuristic fallback. But connecting an LLM via `CognitiveEngine` unlocks substantially better results:

- Richer, context-aware sentiment detection
- More accurate and complete fact extraction
- Better entity recognition beyond regex patterns
- Self-reflective consolidation across conversations
- Cross-episode insight generation

The LLM is not required. It is an upgrade path.


## The Protocol

```python
from soul_protocol import CognitiveEngine

class MyCognitiveEngine:
    async def think(self, prompt: str) -> str:
        # Send prompt to your LLM, return the text response
        ...
```

One async method. Soul Protocol handles all prompt construction, JSON parsing, validation, and fallback logic internally. Your implementation just needs to accept a string and return a string.

The protocol is runtime-checkable (`@runtime_checkable`), so you can verify compliance:

```python
from soul_protocol.cognitive.engine import CognitiveEngine

assert isinstance(my_engine, CognitiveEngine)
```


## LLM Integration Examples

### Claude (Anthropic)

```python
from anthropic import AsyncAnthropic

class ClaudeEngine:
    def __init__(self, model: str = "claude-sonnet-4-5-20250514"):
        self.client = AsyncAnthropic()
        self.model = model

    async def think(self, prompt: str) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

soul = await Soul.birth("Aria", engine=ClaudeEngine())
```

### OpenAI

```python
from openai import AsyncOpenAI

class OpenAIEngine:
    def __init__(self, model: str = "gpt-4o"):
        self.client = AsyncOpenAI()
        self.model = model

    async def think(self, prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

soul = await Soul.birth("Aria", engine=OpenAIEngine())
```

### Ollama (Local)

```python
import httpx

class OllamaEngine:
    def __init__(self, model: str = "llama3"):
        self.model = model

    async def think(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=60.0,
            )
            return r.json()["response"]

soul = await Soul.birth("Aria", engine=OllamaEngine())
```

### Google Gemini

```python
import google.generativeai as genai

class GeminiEngine:
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = genai.GenerativeModel(model)

    async def think(self, prompt: str) -> str:
        response = await self.model.generate_content_async(prompt)
        return response.text

soul = await Soul.birth("Aria", engine=GeminiEngine())
```

All four examples follow the same pattern: wrap your client, implement `think()`, pass the engine at birth. The soul does not care which LLM backs it.


## What the Engine Does

Soul Protocol sends 6 types of cognitive tasks to the engine. Each task is identified by a `[TASK:xxx]` marker in the prompt. The engine does not need to parse this marker -- it is used internally by `HeuristicEngine` for routing.

### 1. Sentiment Detection

**Prompt marker:** `[TASK:sentiment]`

The engine receives text and is asked to return emotional analysis as JSON:

```json
{"valence": -1.0, "arousal": 0.8, "label": "frustration"}
```

Fields:
- `valence`: -1.0 (very negative) to 1.0 (very positive)
- `arousal`: 0.0 (calm) to 1.0 (intense)
- `label`: one of joy, gratitude, curiosity, frustration, confusion, sadness, excitement, neutral

### 2. Significance Assessment

**Prompt marker:** `[TASK:significance]`

The engine evaluates whether an interaction is worth remembering. Context provided includes the soul's core values and recent interactions for novelty comparison.

```json
{"novelty": 0.7, "emotional_intensity": 0.4, "goal_relevance": 0.6, "reasoning": "..."}
```

Each dimension is 0.0 to 1.0. The `reasoning` field is informational -- the soul uses the numeric scores.

### 3. Fact Extraction

**Prompt marker:** `[TASK:extract_facts]`

The engine extracts notable facts about the user from the conversation.

```json
[
    {"content": "User is a backend developer", "importance": 7},
    {"content": "User prefers FastAPI over Django", "importance": 6}
]
```

Returns an empty array `[]` if no notable facts are present. Importance is 1-10.

### 4. Entity Extraction

**Prompt marker:** `[TASK:extract_entities]`

The engine identifies people, technologies, projects, and places mentioned in the conversation.

```json
[
    {"name": "FastAPI", "type": "technology", "relation": "uses"},
    {"name": "PocketPaw", "type": "project", "relation": "builds"}
]
```

Relation values: `uses`, `builds`, `prefers`, `works_at`, `learns`, or `null`.

### 5. Self-Reflection

**Prompt marker:** `[TASK:self_reflection]`

The engine reviews recent interactions and updates the soul's self-concept. It receives the current self-images and recent conversation.

```json
{
    "self_images": [{"domain": "technical_helper", "confidence": 0.7, "reasoning": "..."}],
    "insights": "I'm becoming more of a coding mentor than a general assistant.",
    "relationship_notes": {"user": "Experienced Python developer, prefers concise answers."}
}
```

### 6. Reflection (Consolidation)

**Prompt marker:** `[TASK:reflect]`

The most complex task. The engine reviews the last N episodic memories and the current self-model, then produces a consolidation plan.

```json
{
    "themes": ["Python deployment discussions", "API design patterns"],
    "summaries": [
        {"theme": "deployment", "summary": "Multiple conversations about Docker and CI/CD", "importance": 7}
    ],
    "promote": ["episode_abc123"],
    "emotional_patterns": "User tends to feel frustrated when debugging, but excited when deploying.",
    "self_insight": "I'm most helpful when providing concrete code examples rather than explanations."
}
```

This is the only task that returns `None` in heuristic mode. All other tasks have functional heuristic fallbacks.


## Fallback Chain

The system has a three-layer fallback:

```
LLM returns valid JSON  ->  parse  ->  validate  ->  use
LLM returns bad JSON    ->  parse fails  ->  fall back to heuristic
LLM throws exception    ->  catch  ->  fall back to heuristic
No engine provided       ->  HeuristicEngine (wraps v0.2.0 functions)
```

Every cognitive task is safe to call regardless of engine state. The heuristics produce less nuanced results but are functional and deterministic. This means:

- Tests can run without API keys
- Offline deployments still work
- Cost-sensitive use cases can skip the LLM entirely
- A flaky LLM connection degrades gracefully instead of crashing

JSON parsing is tolerant. The `_parse_json()` helper handles:
1. Direct JSON strings
2. Markdown-fenced code blocks (` ```json ... ``` `)
3. Preamble text before the JSON (finds the first `{` or `[`)


## SearchStrategy

`SearchStrategy` is a separate protocol from `CognitiveEngine`. It controls how memory relevance is scored during retrieval.

**Protocol:**

```python
from soul_protocol.memory.strategy import SearchStrategy

class SearchStrategy(Protocol):
    def score(self, query: str, content: str) -> float: ...
```

One synchronous method (not async -- scoring needs to be fast). Returns 0.0 to 1.0.

**Default:** `TokenOverlapStrategy` computes Jaccard token overlap. Tokens are lowercased, stripped of punctuation, and filtered to 3+ characters. This is zero-dependency and surprisingly effective for keyword-style queries.

**How it plugs into ACT-R:** The strategy replaces the `spreading` component in activation scoring. The full activation formula is:

```
total = W_BASE * base_level + W_SPREAD * strategy.score(query, content) + W_EMOTION * emotional
```

Where `W_SPREAD = 1.5`, giving relevance the highest weight.

**Example: Embedding-based search:**

```python
class EmbeddingSearch:
    def __init__(self, embed_fn):
        self.embed_fn = embed_fn
        self._cache = {}

    def score(self, query: str, content: str) -> float:
        q = self._get_embedding(query)
        c = self._get_embedding(content)
        return float(q @ c / (norm(q) * norm(c)))

    def _get_embedding(self, text: str):
        if text not in self._cache:
            self._cache[text] = self.embed_fn(text)
        return self._cache[text]

soul = await Soul.birth("Aria", search_strategy=EmbeddingSearch(my_embed))
```

Caching matters here because `score()` is called once per candidate memory during recall. With 10,000 episodic entries, that is 10,000 calls per recall.


## HeuristicEngine

The built-in fallback engine. Zero external dependencies. It implements the `CognitiveEngine` protocol by routing prompts based on `[TASK:xxx]` markers to appropriate heuristic functions.

| Task | Heuristic Approach |
|------|-------------------|
| `sentiment` | Word-list scan (~150 words), intensity modifiers, negation detection |
| `significance` | Returns fixed novelty=0.5, computes emotional from sentiment, fixed goal_relevance=0.3 |
| `extract_facts` | Simplified regex (currently only extracts names via `my name is`) |
| `extract_entities` | Returns empty array (entity detection deferred to MemoryManager heuristic) |
| `self_reflection` | Returns minimal placeholder |
| `reflect` | Returns empty result (reflection requires genuine LLM reasoning) |

The `HeuristicEngine` is useful for:

- **Testing:** Deterministic outputs make assertions straightforward
- **Offline deployments:** No network, no API keys, no cost
- **Development:** Fast iteration without LLM latency
- **Fallback:** Automatic safety net when LLM calls fail

When the `CognitiveProcessor` is initialized with just a `HeuristicEngine` (no separate fallback), it takes a fast path. Instead of constructing prompts and parsing JSON responses, it calls the v0.2.0 heuristic functions directly. This avoids unnecessary string serialization/deserialization.


## CognitiveProcessor (Internal)

`CognitiveProcessor` is the internal orchestrator that sits between the soul and the engine. It is not part of the public API, but understanding it is useful for contributors.

Responsibilities:

1. **Prompt construction:** Fills in prompt templates from `cognitive/prompts.py` with interaction data, core values, recent episodes, etc.
2. **Engine dispatch:** Sends constructed prompts to the `CognitiveEngine.think()` method.
3. **Response parsing:** Extracts JSON from LLM responses, handling markdown fences and preamble text.
4. **Validation:** Clamps numeric values to valid ranges (valence to [-1, 1], arousal to [0, 1], etc.).
5. **Fallback routing:** On any exception during LLM processing, falls back to the heuristic implementation.
6. **Fast path:** When running in heuristic-only mode, bypasses prompt construction entirely and calls v0.2.0 functions directly.

The processor is initialized with:

- `engine`: The primary `CognitiveEngine` (LLM or `HeuristicEngine`)
- `fallback`: Optional `HeuristicEngine` for error recovery (only set when primary is an LLM)
- `fact_extractor`: Reference to `MemoryManager.extract_facts` for heuristic fact extraction
- `entity_extractor`: Reference to `MemoryManager.extract_entities` for heuristic entity extraction

The `fact_extractor` and `entity_extractor` callbacks exist because the full heuristic extraction logic lives in `MemoryManager` (where the regex patterns and known tech terms are defined), not in the cognitive module.


## Choosing Between Heuristic and LLM

| Scenario | Recommendation |
|----------|---------------|
| Production with budget | Use an LLM engine. Sentiment, facts, and reflection all benefit substantially. |
| Testing | Use `HeuristicEngine` directly. Deterministic, fast, no API keys. |
| Offline / edge devices | Heuristic-only, or local Ollama engine. |
| Development iteration | Start with heuristic, add LLM when testing real conversations. |
| Cost-sensitive at scale | Heuristic for observe(), LLM only for periodic reflect() calls. |

You can also mix strategies: use a cheap/fast model for sentiment and significance (called on every interaction), and a more capable model for reflection (called periodically).

```python
class TieredEngine:
    def __init__(self, fast_client, smart_client):
        self.fast = fast_client
        self.smart = smart_client

    async def think(self, prompt: str) -> str:
        if "[TASK:reflect]" in prompt or "[TASK:self_reflection]" in prompt:
            return await self.smart.complete(prompt)
        return await self.fast.complete(prompt)
```

This is not a built-in feature -- it is a pattern you can implement in your engine. The protocol's simplicity makes this kind of routing straightforward.
