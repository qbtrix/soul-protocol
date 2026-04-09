# dspy_optimizer.py — Optimization harness for Soul Protocol's DSPy modules.
# Created: feat/dspy-integration — SoulOptimizer uses MIPROv2 to tune
#   significance gating and query expansion against labeled training data
#   derived from ablation study scenarios. Supports save/load of optimized
#   module weights for production deployment.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SoulOptimizer:
    """Optimize Soul Protocol's cognitive modules using DSPy.

    Takes labeled training data (from ablation scenarios or production logs)
    and uses MIPROv2 to find optimal prompts/demonstrations for each module.

    Usage:
        optimizer = SoulOptimizer()
        trainset = optimizer.create_training_data()
        train, val = trainset[:40], trainset[40:]
        optimized_gate = optimizer.optimize_significance_gate(train, val)
        optimizer.save_optimized("optimized_modules/")
    """

    def __init__(self, lm_model: str = "anthropic/claude-haiku-4-5-20251001"):
        """Initialize the optimizer.

        Args:
            lm_model: DSPy-compatible model string for optimization.
                Uses a capable model for the optimizer's teacher LM.
        """
        import dspy

        self._lm = dspy.LM(lm_model)
        dspy.configure(lm=self._lm)

        from soul_protocol.runtime.cognitive.dspy_modules import (
            FactExtractor,
            QueryExpander,
            SignificanceGate,
        )

        self.significance_gate = SignificanceGate()
        self.query_expander = QueryExpander()
        self.fact_extractor = FactExtractor()

        self._optimized_gate = None
        self._optimized_expander = None
        self._optimized_extractor = None

    def create_training_data(
        self,
        scenarios_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """Generate training data from ablation scenarios.

        Labels each interaction as worth-storing or not based on:
        - Does it contain a planted fact? -> should_store=True
        - Is it filler/small talk? -> should_store=False
        - Does it have emotional content? -> should_store=True

        Args:
            scenarios_path: Optional path to a JSON file with custom scenarios.
                If None, generates from the built-in research scenarios.

        Returns:
            List of labeled training examples as dicts with keys:
            user_input, agent_output, core_values, should_store,
            expected_facts, recall_queries.
        """
        if scenarios_path:
            data = json.loads(Path(scenarios_path).read_text())
            return data

        # Generate from built-in scenarios
        examples: list[dict[str, Any]] = []
        try:
            from research.agents import UserProfile
            from research.scenarios import generate_scenarios
        except ImportError:
            # Research module not available — return empty
            return examples

        use_cases = ["support", "coding", "companion", "knowledge"]
        for use_case in use_cases:
            for uid in range(5):
                user = UserProfile(user_id=uid, persona=use_case)
                scenarios = generate_scenarios(user, use_case, seed=42)

                for scenario in scenarios:
                    for i, turn in enumerate(scenario.turns):
                        # Label: should_store if contains fact, strong emotion,
                        # or is within 2 turns of a planted fact
                        near_fact = any(
                            abs(i - j) <= 2 for j, t in enumerate(scenario.turns) if t.contains_fact
                        )
                        should_store = (
                            turn.contains_fact
                            or near_fact
                            or turn.importance_hint >= 0.7
                            or bool(turn.expected_emotion)
                        )

                        example = {
                            "user_input": turn.user_input,
                            "agent_output": turn.agent_output,
                            "core_values": ["helpfulness", "empathy", "accuracy"],
                            "should_store": should_store,
                            "contains_fact": turn.contains_fact,
                            "fact_content": turn.fact_content,
                            "importance_hint": turn.importance_hint,
                            "expected_emotion": turn.expected_emotion,
                        }
                        examples.append(example)

                    # Add recall query expansion examples
                    for query, expected in scenario.recall_queries:
                        examples.append(
                            {
                                "type": "recall",
                                "query": query,
                                "expected_fact": expected,
                                "planted_facts": scenario.planted_facts,
                            }
                        )

        return examples

    def optimize_significance_gate(
        self,
        trainset: list[Any],
        valset: list[Any],
        max_trials: int = 50,
    ) -> Any:
        """Optimize the significance gate using MIPROv2.

        Args:
            trainset: Training examples (dspy.Example objects or dicts).
            valset: Validation examples for metric evaluation.
            max_trials: Maximum optimization trials (higher = better but slower).

        Returns:
            The optimized DSPy module.
        """
        import dspy

        # Convert dicts to dspy.Example if needed
        train_examples = [
            self._to_significance_example(e)
            for e in trainset
            if not isinstance(e, dict) or e.get("type") != "recall"
        ]

        optimizer = dspy.MIPROv2(
            metric=self._significance_metric,
            max_bootstrapped_demos=4,
            num_threads=4,
        )
        self._optimized_gate = optimizer.compile(
            self.significance_gate._module,
            trainset=train_examples,
            max_bootstrapped_demos=4,
            max_labeled_demos=8,
        )
        return self._optimized_gate

    def optimize_query_expander(
        self,
        trainset: list[Any],
        valset: list[Any],
        max_trials: int = 30,
    ) -> Any:
        """Optimize query expansion for better recall.

        Args:
            trainset: Training examples with query + expected matches.
            valset: Validation examples.
            max_trials: Maximum optimization trials.

        Returns:
            The optimized DSPy module.
        """
        import dspy

        recall_train = [
            self._to_recall_example(e)
            for e in trainset
            if isinstance(e, dict) and e.get("type") == "recall"
        ]

        if not recall_train:
            return self.query_expander._module

        optimizer = dspy.MIPROv2(
            metric=self._recall_metric,
            max_bootstrapped_demos=3,
            num_threads=4,
        )
        self._optimized_expander = optimizer.compile(
            self.query_expander._module,
            trainset=recall_train,
            max_bootstrapped_demos=3,
            max_labeled_demos=6,
        )
        return self._optimized_expander

    def _significance_metric(
        self,
        example: Any,
        prediction: Any,
        trace: Any = None,
    ) -> float:
        """Score: did the gate correctly classify this interaction?

        Returns 1.0 for correct classification, 0.0 for incorrect.
        Partial credit for borderline cases with good reasoning.
        """
        expected = bool(getattr(example, "should_store", True))
        predicted = bool(getattr(prediction, "should_store", True))

        if predicted == expected:
            score = 1.0
            # Bonus for good reasoning
            reasoning = str(getattr(prediction, "reasoning", ""))
            if len(reasoning) > 20:
                score += 0.1
            return min(1.0, score)

        return 0.0

    def _recall_metric(
        self,
        example: Any,
        prediction: Any,
        trace: Any = None,
    ) -> float:
        """Score: do expanded queries cover the expected fact?

        Checks if any expanded query has token overlap with the expected fact.
        """
        expected = str(getattr(example, "expected_fact", "")).lower()
        expanded = getattr(prediction, "expanded_queries", [])

        if not expected:
            return 1.0

        expected_tokens = set(expected.split())
        for query in expanded:
            query_tokens = set(str(query).lower().split())
            overlap = len(expected_tokens & query_tokens) / max(len(expected_tokens), 1)
            if overlap > 0.3:
                return 1.0

        return 0.0

    def _to_significance_example(self, data: Any) -> Any:
        """Convert a dict or existing example to a dspy.Example."""
        import dspy

        if isinstance(data, dict):
            return dspy.Example(
                user_input=data.get("user_input", ""),
                agent_output=data.get("agent_output", ""),
                core_values=data.get("core_values", []),
                recent_context="",
                should_store=data.get("should_store", True),
            ).with_inputs("user_input", "agent_output", "core_values", "recent_context")
        return data

    def _to_recall_example(self, data: Any) -> Any:
        """Convert a dict to a dspy.Example for recall optimization."""
        import dspy

        if isinstance(data, dict):
            return dspy.Example(
                query=data.get("query", ""),
                personality_summary="",
                expected_fact=data.get("expected_fact", ""),
                planted_facts=data.get("planted_facts", []),
            ).with_inputs("query", "personality_summary")
        return data

    def save_optimized(self, path: str) -> None:
        """Save optimized modules for production use.

        Args:
            path: Directory to save optimized module weights to.
        """
        base = Path(path)
        base.mkdir(parents=True, exist_ok=True)

        if self._optimized_gate:
            self._optimized_gate.save(str(base / "significance_gate.json"))
        if self._optimized_expander:
            self._optimized_expander.save(str(base / "query_expander.json"))
        if self._optimized_extractor:
            self._optimized_extractor.save(str(base / "fact_extractor.json"))

        # Save metadata
        meta = {
            "version": "0.1.0",
            "modules": {
                "significance_gate": self._optimized_gate is not None,
                "query_expander": self._optimized_expander is not None,
                "fact_extractor": self._optimized_extractor is not None,
            },
        }
        (base / "meta.json").write_text(json.dumps(meta, indent=2))

    def load_optimized(self, path: str) -> None:
        """Load previously optimized modules.

        Args:
            path: Directory containing optimized module JSON files.
        """
        base = Path(path)
        if (base / "significance_gate.json").exists():
            self.significance_gate._module.load(str(base / "significance_gate.json"))
        if (base / "query_expander.json").exists():
            self.query_expander._module.load(str(base / "query_expander.json"))
        if (base / "fact_extractor.json").exists():
            self.fact_extractor._module.load(str(base / "fact_extractor.json"))
