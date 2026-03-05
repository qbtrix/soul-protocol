# tests/test_memory/test_search_improvements.py — Tests for tokenizer and synonym
# recall improvements (issues #10 and #11).
# Created: 2026-03-02 — Verifies:
#   - Tokenizer splits on /, _, -, . separators (not just whitespace)
#   - Synonym expansion maps common programming terms to related aliases
#   - relevance_score finds memories with related (synonym) terms
#   - Edge cases: empty input, short tokens, overlapping synonym groups

from __future__ import annotations

from soul_protocol.memory.search import (
    _SYNONYM_MAP,
    _expand_synonyms,
    relevance_score,
    tokenize,
)

# ===========================================================================
# Bug #11 — Tokenizer should split on /, _, -, .
# ===========================================================================


class TestTokenizerSplitsOnSeparators:
    """tokenize() must split on /, _, -, and . in addition to whitespace."""

    def test_split_on_forward_slash(self):
        """File paths like 'app/routes/handler' produce individual tokens."""
        tokens = tokenize("app/routes/handler")
        assert "app" in tokens
        assert "routes" in tokens
        assert "handler" in tokens

    def test_split_on_underscore(self):
        """Snake_case identifiers like 'user_session_token' are split."""
        tokens = tokenize("user_session_token")
        assert "user" in tokens
        assert "session" in tokens
        assert "token" in tokens

    def test_split_on_hyphen(self):
        """Kebab-case like 'my-cool-project' is split."""
        tokens = tokenize("my-cool-project")
        # 'my' is < 3 chars, should be filtered out
        assert "my" not in tokens
        assert "cool" in tokens
        assert "project" in tokens

    def test_split_on_dot(self):
        """Dotted names like 'os.environ.get' are split."""
        tokens = tokenize("os.environ.get")
        # 'os' is < 3 chars, 'get' is exactly 3
        assert "os" not in tokens
        assert "environ" in tokens
        assert "get" in tokens

    def test_mixed_separators(self):
        """Complex paths with mixed separators produce all components."""
        tokens = tokenize("src/soul_protocol/memory/search.py")
        assert "src" in tokens
        assert "soul" in tokens
        assert "protocol" in tokens
        assert "memory" in tokens
        assert "search" in tokens
        # 'py' is < 3 chars
        assert "py" not in tokens

    def test_whitespace_still_works(self):
        """Basic whitespace splitting still works as before."""
        tokens = tokenize("hello world foo")
        assert "hello" in tokens
        assert "world" in tokens
        assert "foo" in tokens

    def test_combined_whitespace_and_separators(self):
        """Whitespace + separators in same string both trigger splits."""
        tokens = tokenize("check app/routes for user_data")
        assert "check" in tokens
        assert "app" in tokens
        assert "routes" in tokens
        assert "for" in tokens  # exactly 3 chars, passes len >= 3 filter
        assert "user" in tokens
        assert "data" in tokens

    def test_consecutive_separators(self):
        """Multiple consecutive separators don't produce empty tokens."""
        tokens = tokenize("foo//bar__baz--qux..quux")
        assert "foo" in tokens
        assert "bar" in tokens
        assert "baz" in tokens
        assert "qux" in tokens
        assert "quux" in tokens
        assert "" not in tokens

    def test_file_extension_split(self):
        """File extensions like '.py' are split from the filename."""
        tokens = tokenize("handler.py")
        assert "handler" in tokens
        # 'py' is < 3 chars, filtered out
        assert "py" not in tokens

    def test_real_world_path(self):
        """A realistic project path produces searchable tokens."""
        tokens = tokenize("src/soul_protocol/memory/search.py")
        # All meaningful components should be present
        for expected in ("src", "soul", "protocol", "memory", "search"):
            assert expected in tokens, f"Expected '{expected}' in tokens from path"


# ===========================================================================
# Bug #10 — Synonym / alias expansion for improved recall
# ===========================================================================


class TestSynonymExpansion:
    """_expand_synonyms() adds related terms from the synonym map."""

    def test_database_synonyms(self):
        """'database' expands to include sql, postgresql, etc."""
        expanded = _expand_synonyms({"database"})
        assert "sql" in expanded
        assert "postgresql" in expanded
        assert "postgres" in expanded
        assert "mysql" in expanded
        assert "sqlite" in expanded
        assert "database" in expanded  # original preserved

    def test_reverse_synonym(self):
        """'sql' expands to include 'database' — synonyms are bidirectional."""
        expanded = _expand_synonyms({"sql"})
        assert "database" in expanded

    def test_no_synonyms_passthrough(self):
        """Tokens without synonym entries pass through unchanged."""
        expanded = _expand_synonyms({"banana", "smoothie"})
        assert expanded == {"banana", "smoothie"}

    def test_empty_set(self):
        """Empty input returns empty output."""
        assert _expand_synonyms(set()) == set()

    def test_multiple_tokens_some_with_synonyms(self):
        """Only tokens in the map get expanded; others pass through."""
        expanded = _expand_synonyms({"database", "banana"})
        assert "banana" in expanded
        assert "sql" in expanded
        assert "database" in expanded

    def test_python_synonyms(self):
        """'python' and 'pip' are in the same synonym group."""
        expanded = _expand_synonyms({"python"})
        assert "pip" in expanded

    def test_deploy_synonyms(self):
        """'deploy' expands to 'deployment' and 'shipping'."""
        expanded = _expand_synonyms({"deploy"})
        assert "deployment" in expanded
        assert "shipping" in expanded

    def test_auth_synonyms(self):
        """'auth' expands to 'authentication' and 'login'."""
        expanded = _expand_synonyms({"auth"})
        assert "authentication" in expanded
        assert "login" in expanded

    def test_synonym_map_is_symmetric(self):
        """Every term in a synonym group points to the same full group."""
        for term, group in _SYNONYM_MAP.items():
            assert term in group, f"Term '{term}' not in its own group"
            for peer in group:
                assert peer in _SYNONYM_MAP, f"Peer '{peer}' missing from map"
                assert _SYNONYM_MAP[peer] == group, (
                    f"Asymmetric synonym groups: _SYNONYM_MAP['{term}'] != _SYNONYM_MAP['{peer}']"
                )


# ===========================================================================
# Integration — relevance_score with improved tokenizer + synonyms
# ===========================================================================


class TestRelevanceScoreWithImprovements:
    """relevance_score() benefits from both the tokenizer fix and synonyms."""

    def test_file_path_query_matches_content(self):
        """Querying 'routes' matches content with 'app/routes/handler'."""
        score = relevance_score("routes", "Code is in app/routes/handler")
        assert score > 0.0

    def test_underscore_identifier_match(self):
        """Querying 'session' matches content with 'user_session_token'."""
        score = relevance_score("session", "Check the user_session_token value")
        assert score > 0.0

    def test_synonym_database_matches_postgresql(self):
        """Querying 'database' matches content mentioning 'PostgreSQL'."""
        score = relevance_score(
            "database setup",
            "Project uses FastAPI framework with PostgreSQL backend",
        )
        assert score > 0.0, (
            "Expected 'database' to partially match content with 'PostgreSQL' via synonym expansion"
        )

    def test_synonym_db_matches_database(self):
        """Querying 'db' (short for database) — too short, filtered by len >= 3."""
        # 'db' is 2 chars, should be dropped by tokenizer.
        # This test documents the expected behavior.
        score = relevance_score("db config", "database configuration file")
        # 'db' dropped (< 3 chars), 'config' matches 'config' via synonym expansion
        assert score > 0.0  # 'config' → 'configuration' synonym match

    def test_synonym_deploy_matches_deployment(self):
        """Querying 'deploy' matches content with 'deployment'."""
        score = relevance_score("deploy", "The deployment process uses Docker")
        assert score > 0.0

    def test_synonym_test_matches_pytest(self):
        """Querying 'test' matches content with 'pytest'."""
        score = relevance_score("test suite", "Run pytest to validate the code")
        assert score > 0.0

    def test_no_match_still_zero(self):
        """Unrelated content still scores 0.0."""
        score = relevance_score("quantum physics", "banana smoothie recipe")
        assert score == 0.0

    def test_empty_query_still_zero(self):
        """Empty query still returns 0.0."""
        assert relevance_score("", "some content") == 0.0

    def test_exact_match_still_one(self):
        """Exact token match still scores 1.0."""
        score = relevance_score("python programming", "python programming")
        assert score == 1.0

    def test_path_components_all_searchable(self):
        """Each component of a dotted/slashed path is independently searchable."""
        content = "Config lives in src/soul_protocol/memory/search.py"
        assert relevance_score("soul", content) > 0.0
        assert relevance_score("protocol", content) > 0.0
        assert relevance_score("memory", content) > 0.0
        assert relevance_score("search", content) > 0.0

    def test_synonym_does_not_inflate_score_above_one(self):
        """Synonym expansion doesn't push scores above 1.0."""
        score = relevance_score("database", "database sql postgresql mysql sqlite")
        assert score <= 1.0

    def test_docker_matches_container(self):
        """Querying 'docker' matches content about 'container'."""
        score = relevance_score(
            "docker setup",
            "The container orchestration uses Kubernetes",
        )
        assert score > 0.0

    def test_auth_matches_login(self):
        """Querying 'authentication' matches content about 'login'."""
        score = relevance_score(
            "authentication flow",
            "The login page handles user credentials",
        )
        assert score > 0.0
