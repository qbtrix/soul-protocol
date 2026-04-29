---
{
  "title": "LiteLLM Cognitive Engine — Multi-Model Proxy Backend",
  "summary": "An async `CognitiveEngine` implementation that routes LLM calls through a LiteLLM OpenAI-compatible proxy, enabling the research framework to use GPT-4o, Gemini, DeepSeek, Llama, and Qwen as judge or agent engines without changing call sites. It mirrors the `HaikuCognitiveEngine` interface exactly, making the two engines interchangeable.",
  "concepts": [
    "LiteLLM",
    "multi-model",
    "OpenAI-compatible",
    "proxy",
    "CognitiveEngine",
    "think protocol",
    "judge engine",
    "Gemini",
    "DeepSeek",
    "Llama",
    "inter-rater reliability",
    "asyncio",
    "semaphore",
    "UsageTracker",
    "temperature"
  ],
  "categories": [
    "research",
    "llm-backend",
    "multi-model",
    "soul-protocol"
  ],
  "source_docs": [
    "f826546e10dfc0e7"
  ],
  "backlinks": null,
  "word_count": 380,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`LiteLLMEngine` was built to support the multi-judge validation methodology. Soul Protocol's research design requires that quality scores be consistent across multiple judge models — if only Haiku judged responses, reviewer skepticism about model-specific biases would be valid. By routing Gemini, DeepSeek, and Llama through a LiteLLM proxy, the same `think(prompt)` interface works for all models.

## Interface Compatibility

The engine implements the same `async def think(self, prompt: str) -> str` protocol as `HaikuCognitiveEngine`. Research components like `ResponseJudge` and `MultiConditionResponder` accept either engine without modification.

## OpenAI-Compatible Endpoint

`LiteLLMEngine` uses `openai.AsyncOpenAI` pointed at a LiteLLM proxy URL rather than the official OpenAI API:

```python
self._client = AsyncOpenAI(
    base_url=base_url or os.environ.get("LITELLM_PROXY_URL", "https://litellm.hzd.interacly.com"),
    api_key=api_key or os.environ.get("LITELLM_API_KEY", ""),
)
```

LiteLLM translates the OpenAI chat completions format to each model's native API, so the research code never needs to know whether it is calling Gemini or DeepSeek.

## Concurrency Control

A semaphore (default `max_concurrent=10`, half of Haiku's 20) limits parallel calls. The lower default reflects that the LiteLLM proxy has its own upstream rate limits that vary by model and are harder to predict than Anthropic's.

## Temperature and Token Limits

The engine accepts a `temperature` parameter (default 0.3). Lower temperature makes judge outputs more deterministic and reproducible across runs, which matters for inter-rater reliability analysis.

## Usage Tracking

`UsageTracker` here is a simplified version of the one in `haiku_engine.py` — it tracks calls, token counts, and elapsed time but omits the cost calculation (model pricing varies too widely across the LiteLLM catalog to embed). The `.summary()` method still gives throughput and error-rate visibility.

## Error Handling

Unlike the Haiku engine, `LiteLLMEngine` does not retry. Errors are caught, the counter is incremented, and a `RuntimeError` with model name and original message is raised. This is intentional: the multi-judge runner wraps each test in a try/except and records "ERR" for that cell in the scorecard rather than retrying, keeping the run moving.

## Known Gaps

- **No retry logic**: A transient proxy timeout fails immediately, which may skew inter-rater agreement tables if one judge consistently errors.
- **No cost tracking**: The simplified `UsageTracker` cannot produce an estimated cost for non-Haiku models.
- The proxy URL defaults to a hardcoded internal endpoint (`litellm.hzd.interacly.com`), which will fail in environments without VPN access to that host.