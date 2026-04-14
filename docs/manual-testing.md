<!--
manual-testing.md — Hands-on validation guide for the v0.3 org-layer primitives.
Eight use-case scenarios end-to-end: bootstrap, journal queries, decision traces,
retrieval router, credential broker, undeletability, status/destroy, teardown.
Companion to docs/architecture.md sections 7-12.
-->

# Manual Testing Guide — v0.3 Org Layer

> Hands-on validation of the journal, root agent, retrieval router, credential broker, and decision traces. Written for humans (and curious agents) who want to touch the primitives before they go to production.

> **Note on CLI names:** commands below use `soul paw os init / status / destroy` and the `~/.pocketpaw/` data directory because that's the current branch state. A cleanup PR is pending that renames these to `soul org init / status / destroy` with `~/.soul/` default (see the org-journal-spec.md positioning). When that lands, swap the commands below accordingly — the semantics are unchanged.

**Prerequisites:**

```bash
cd /path/to/soul-protocol
git fetch origin
git checkout feat/onboarding-full    # the tip of the v0.3 stack (PR #170)
uv sync
uv run pytest tests/ --ignore=tests/test_cognitive_adapters.py --ignore=tests/test_mcp_sampling_engine.py
# Should see ~1976 passed. The two ignored files have pre-existing import issues unrelated to v0.3.
```

> **Tip:** if you want the final merged behavior, use the topmost branch of the stack. Each earlier branch in the stack supports a subset of the features below.

---

## Use Case 1 — Fresh Org Bootstrap

**Goal:** create a new Paw OS org from nothing. Verify the genesis event, scope tree, and root soul are all in place.

### Steps

```bash
# 1. Pick a fresh data dir (don't run this against your actual ~/.pocketpaw!)
export PAW_TEST_DIR=/tmp/paw-manual-test
rm -rf $PAW_TEST_DIR

# 2. Run the interactive wizard
uv run soul paw os init --data-dir $PAW_TEST_DIR

# Prompts:
#   Org name: Acme Test Org
#   Purpose: A sandbox for kicking the tires
#   Values (comma-separated): curiosity, honesty, speed
#   Founder name: Alice
#   Founder email: alice@acme.test
#   First-level scopes (comma-separated, max 5): org:sales, org:ops, org:me
#   Starter fleet (Sales/Support/Solo/Skip): Solo
```

### What to check

```bash
# Files created
ls -la $PAW_TEST_DIR/org/
# Expect: root.soul, journal.db, keys/root.ed25519

# Key has the right permissions
stat -f '%Sp' $PAW_TEST_DIR/org/keys/root.ed25519
# Expect: -rw------- (0600)

# User soul exists
ls $PAW_TEST_DIR/users/
# Expect: alice.soul

# Status reports the org
uv run soul paw os status --data-dir $PAW_TEST_DIR

# Expect output includes:
#   Org: Acme Test Org
#   Values: curiosity, honesty, speed
#   Root DID: did:soul:<hash>
#   Event count: 6+ (org.created, values_set, user.joined, user.admin_granted,
#                    3x scope.created, agent.spawned stub)
```

### Alternative: non-interactive flow

```bash
rm -rf $PAW_TEST_DIR
uv run soul paw os init \
  --data-dir $PAW_TEST_DIR \
  --non-interactive \
  --org-name "Acme" \
  --purpose "Sandbox" \
  --values "curiosity,speed" \
  --founder-name "Alice" \
  --founder-email "alice@acme.test" \
  --scopes "org:sales,org:ops" \
  --fleet "Solo"
```

### Pass/fail signals

| Signal | Pass | Fail |
|--------|------|------|
| Exit code | 0 | anything else |
| `journal.db` size | non-zero | empty or missing |
| Key permissions | `-rw-------` | anything wider |
| Re-running without `--force` | refuses with clear error | overwrites or silently succeeds |

---

## Use Case 2 — Query the Journal Directly

**Goal:** prove the journal is queryable, scope filtering works, and events round-trip cleanly.

### Steps

```python
# Open a python REPL from the repo root
uv run python

# Inside REPL:
from pathlib import Path
from soul_protocol.engine.journal import open_journal
from soul_protocol.spec.journal import Actor

journal = open_journal(Path("/tmp/paw-manual-test/org/journal.db"))

# All events
all_events = journal.query(limit=100)
print(f"Total events: {len(all_events)}")
for e in all_events:
    print(f"  {e.ts.isoformat()}  {e.action:30s}  scope={e.scope}")

# Filter by action
org_created = journal.query(action="org.created")
assert len(org_created) == 1, "exactly one genesis event"
print(f"Genesis: {org_created[0].payload}")

# Filter by scope
sales_events = journal.query(scope=["org:sales:*"])
print(f"Sales-scoped events: {len(sales_events)}")

# Filter by time (remember: must be tz-aware)
from datetime import datetime, timedelta, UTC
recent = journal.query(since=datetime.now(UTC) - timedelta(hours=1))
print(f"Events in last hour: {len(recent)}")

# Naive datetime should raise
try:
    journal.query(since=datetime.now())  # no tzinfo
    print("BUG: should have raised")
except (ValueError, TypeError) as e:
    print(f"Correctly rejected naive datetime: {e}")
```

### Pass/fail signals

| Signal | Pass | Fail |
|--------|------|------|
| Total events | matches `paw os status` count | mismatch |
| Genesis event payload | has org_name, purpose, created_by_user | missing fields |
| Scope filter | only sales-scoped events returned | unrelated events leak in |
| Naive datetime | raises | silently accepts |

---

## Use Case 3 — Record a Decision Trace

**Goal:** record an `agent.proposed` → `human.corrected` pair and verify the causation chain.

### Steps

```python
# Continue in the REPL from Use Case 2

from uuid import uuid4
from datetime import datetime, UTC
from soul_protocol.spec.journal import Actor, EventEntry
from soul_protocol.spec.decisions import (
    AgentProposal, HumanCorrection,
    build_proposal_event, build_correction_event,
    find_corrections_for, trace_decision_chain,
)

agent_actor = Actor(kind="agent", id="did:soul:sales-draft-bot", scope_context=["org:sales:*"])
user_actor = Actor(kind="user", id="alice", scope_context=["org:*"])
session_id = uuid4()

# 1. Agent proposes a draft email
proposal = AgentProposal(
    proposal_kind="message_draft",
    summary="Follow-up to Acme after last week's call — asking about Q3 timeline.",
    proposal={
        "to": "cto@acme.example",
        "subject": "Checking in on Q3 timeline",
        "body": "Dear CTO,\n\nHope you're doing well. Per our chat last week, ...",
    },
    confidence=0.82,
    alternatives=[],
    context_refs=[],
)

proposal_event = build_proposal_event(
    actor=agent_actor,
    scope=["org:sales:leads"],
    correlation_id=session_id,
    proposal=proposal,
)
journal.append(proposal_event)
print(f"Proposed: {proposal_event.id}")

# 2. Human edits the draft (too formal, removed "Dear CTO")
correction = HumanCorrection(
    disposition="edited",
    corrected_value={
        "to": "cto@acme.example",
        "subject": "Checking in",
        "body": "Hi — quick nudge on the Q3 timeline...",
    },
    correction_reason="Tone was too formal for the relationship we have with them.",
    structured_reason_tags=["tone_too_formal", "remove_salutation"],
    edit_distance=0.41,
)

correction_event = build_correction_event(
    actor=user_actor,
    scope=["org:sales:leads"],
    correlation_id=session_id,
    causation_id=proposal_event.id,
    correction=correction,
)
journal.append(correction_event)
print(f"Corrected: {correction_event.id}")

# 3. Verify the chain
corrections = find_corrections_for(journal, proposal_event.id)
assert len(corrections) == 1
assert corrections[0].payload["disposition"] == "edited"

chain = trace_decision_chain(journal, session_id)
print(f"Decision chain for session {session_id}:")
for e in chain:
    print(f"  {e.action:20s}  {e.id}")
```

### Pass/fail signals

| Signal | Pass | Fail |
|--------|------|------|
| Both events appended | succeeds, no exceptions | raises |
| `find_corrections_for` | returns exactly 1 correction | returns 0, returns unrelated events |
| `trace_decision_chain` | returns [proposal, correction] in chronological order | wrong order, missing events |
| `causation_id` linkage | correction's causation_id == proposal.id | mismatch or None |

### Stretch: simulate pattern detection

Append 3 more corrections with the `tone_too_formal` tag, then:

```python
from soul_protocol.spec.decisions import cluster_correction_patterns
clusters = cluster_correction_patterns(journal, min_occurrences=3)
for c in clusters:
    print(f"  tags={c['tags']}  count={c['count']}  recent={c['recent_ts']}")
```

Expect a cluster on `('remove_salutation', 'tone_too_formal')` with count >= 3.

---

## Use Case 4 — Retrieval Router Dispatch

**Goal:** dispatch a query across two mock sources, verify scope filtering and audit emission.

### Steps

```python
# Continue in REPL (or new session with journal reopened)

from soul_protocol.spec.retrieval import (
    CandidateSource, RetrievalRequest, RetrievalCandidate,
)
from soul_protocol.engine.retrieval import (
    RetrievalRouter, InMemoryCredentialBroker, MockAdapter, ProjectionAdapter,
)

# Broker + router
broker = InMemoryCredentialBroker(journal=journal)
router = RetrievalRouter(journal=journal, broker=broker)

# Register two mock sources — one in sales scope, one in support
sales_adapter = MockAdapter(candidates=[
    RetrievalCandidate(
        source="mock_sales",
        content={"doc": "Acme Q3 pipeline forecast"},
        score=0.9,
        as_of=datetime.now(UTC),
        cached=False,
    ),
])
support_adapter = MockAdapter(candidates=[
    RetrievalCandidate(
        source="mock_support",
        content={"doc": "Widget outage retrospective"},
        score=0.8,
        as_of=datetime.now(UTC),
        cached=False,
    ),
])

router.register_source(
    CandidateSource(name="mock_sales", kind="projection", scopes=["org:sales:*"], adapter_ref="mock"),
    sales_adapter,
)
router.register_source(
    CandidateSource(name="mock_support", kind="projection", scopes=["org:support:*"], adapter_ref="mock"),
    support_adapter,
)

# Query with sales scope — should only hit the sales adapter
request = RetrievalRequest(
    query="Q3 pipeline",
    actor=user_actor,
    scopes=["org:sales:*"],
    strategy="parallel",
    limit=10,
    timeout_s=5.0,
)
result = router.dispatch(request)

print(f"Sources queried: {result.sources_queried}")
print(f"Sources failed:  {result.sources_failed}")
print(f"Candidates:      {len(result.candidates)}")
for c in result.candidates:
    print(f"  [{c.source}] score={c.score}  content={c.content}")

# Verify journal captured the retrieval
retrievals = journal.query(action="retrieval.query", limit=5)
print(f"retrieval.query events recorded: {len(retrievals)}")
```

### Pass/fail signals

| Signal | Pass | Fail |
|--------|------|------|
| `sources_queried` | `["mock_sales"]` only | includes mock_support (scope leak) |
| Candidates count | 1 | 0 or 2 (filter failure) |
| Journal retrieval event | 1+ new `retrieval.query` event with scope `["org:sales:*"]` | 0 events |
| Adapter invocation | `sales_adapter.invocations == 1` | 0 (no dispatch) or >1 (double-dispatch) |

### Stretch: `first` vs `parallel` vs `sequential`

Repeat with `strategy="first"` and `strategy="sequential"` on a scope that matches both adapters (`["org:*"]`). Observe how candidate counts and latencies differ.

### Stretch: timeout behavior

Make one adapter slow:

```python
import time
class SlowAdapter(MockAdapter):
    def query(self, request, credential):
        time.sleep(2.0)
        return super().query(request, credential)

router.register_source(
    CandidateSource(name="slow", kind="projection", scopes=["org:*"], adapter_ref="slow"),
    SlowAdapter(candidates=[]),
)

result = router.dispatch(RetrievalRequest(
    query="anything",
    actor=user_actor,
    scopes=["org:*"],
    strategy="parallel",
    timeout_s=1.0,
))
print(f"sources_failed: {result.sources_failed}")
# Expect: [('slow', 'timeout')] or similar
```

---

## Use Case 5 — Credential Broker Lifecycle

**Goal:** prove credential scoping, expiry, and audit emission.

### Steps

```python
# Fresh credential
cred = broker.acquire(source="drive", scopes=["org:sales:*"], ttl_s=5)
print(f"Acquired: {cred.id}  expires={cred.expires_at.isoformat()}")

# Use from correct scope — should succeed
broker.ensure_usable(cred, requester_scopes=["org:sales:leads"])
broker.mark_used(cred)
print("Used from org:sales:leads — OK")

# Use from wrong scope — should raise
from soul_protocol.engine.retrieval.exceptions import CredentialScopeError
try:
    broker.ensure_usable(cred, requester_scopes=["org:support:*"])
    print("BUG: should have raised")
except CredentialScopeError as e:
    print(f"Correctly rejected cross-scope use: {e}")

# Wait for expiry and try again
import time
time.sleep(6)
try:
    broker.ensure_usable(cred, requester_scopes=["org:sales:*"])
    print("BUG: should have raised (expired)")
except Exception as e:
    print(f"Correctly rejected expired credential: {e}")

# Verify audit events
audit = journal.query(action="credential.acquired", limit=10)
used = journal.query(action="credential.used", limit=10)
expired = journal.query(action="credential.expired", limit=10)
print(f"acquired={len(audit)}  used={len(used)}  expired={len(expired)}")
```

### Pass/fail signals

| Signal | Pass | Fail |
|--------|------|------|
| Acquire emits `credential.acquired` | 1 new event | 0 events |
| Same-scope use | succeeds | raises |
| Cross-scope use | raises `CredentialScopeError` | succeeds (security failure) |
| Expired use | raises | succeeds (bypassed TTL) |
| `mark_used` emits `credential.used` | 1 new event per mark | 0 or duplicates |
| Expiry emits `credential.expired` once | exactly 1 event | 0 or repeated |

---

## Use Case 6 — Root Undeletability

**Goal:** prove the three-layer undeletability guard actually works.

### Steps

```bash
# Layer 3 — CLI guard
uv run soul delete $PAW_TEST_DIR/org/root.soul

# Expect: non-zero exit, error message mentioning role=root or SoulProtectedError

# Layer 1 — file-level guard (programmatic)
uv run python -c "
from soul_protocol.core.soul import Soul
from soul_protocol.exceptions import SoulProtectedError
soul = Soul.awaken('$PAW_TEST_DIR/org/root.soul')
try:
    soul.delete()
    print('BUG: should have raised SoulProtectedError')
except SoulProtectedError as e:
    print(f'Correctly blocked delete: {e}')
"

# Layer 2 — protocol guard
uv run python -c "
from uuid import uuid4
from datetime import datetime, UTC
from soul_protocol.spec.journal import EventEntry, Actor
from soul_protocol.core.soul import Soul
# ... load the journal and root DID as above ...
root = Soul.awaken('$PAW_TEST_DIR/org/root.soul')
root_did = root.identity.did
# Attempt to forge an agent.retired event targeting root
evt = EventEntry(
    id=uuid4(),
    ts=datetime.now(UTC),
    actor=Actor(kind='user', id='malicious_admin', scope_context=['org:*']),
    action='agent.retired',
    scope=['org:*'],
    payload={'target_did': root_did},
)
from soul_protocol.spec.journal import check_root_undeletable
try:
    check_root_undeletable(evt, root_did)
    print('BUG: should have raised')
except Exception as e:
    print(f'Correctly rejected: {e}')
"

# Positive case: non-root delete should work
uv run python -c "
from soul_protocol.core.soul import Soul
non_root = Soul.awaken('$PAW_TEST_DIR/users/alice.soul')
non_root.delete()  # should succeed
print('Non-root delete: OK')
"
```

### Pass/fail signals

| Signal | Pass | Fail |
|--------|------|------|
| `soul delete` on root.soul | non-zero exit, clear error | succeeds (root deleted — catastrophic) |
| Programmatic `.delete()` on root | raises `SoulProtectedError` | succeeds |
| Forged `agent.retired` for root | rejected by `check_root_undeletable` | accepted |
| Non-root `.delete()` | succeeds | regressed existing behavior |

---

## Use Case 7 — Status + Destroy Lifecycle

**Goal:** verify status reports accurate state and destroy is irreversible-but-archived.

### Steps

```bash
# Snapshot state
uv run soul paw os status --data-dir $PAW_TEST_DIR --json > /tmp/status-before.json
cat /tmp/status-before.json

# Try to destroy without flags — should refuse
uv run soul paw os destroy --data-dir $PAW_TEST_DIR
# Expect: non-zero exit, message about required flags

# Try with one flag — should still refuse
uv run soul paw os destroy --data-dir $PAW_TEST_DIR --confirm
# Expect: non-zero exit

# Interactive mode with both flags — expects typed org-name confirmation
uv run soul paw os destroy --data-dir $PAW_TEST_DIR --confirm --i-mean-it
# Prompt: "Type the org name to confirm: " — type "Acme Test Org"
# Expect: tarball created, dir wiped

# Verify archive exists
ls -la ~/.pocketpaw/archives/
# Expect: a file like org-destroyed-20260413-<time>.tar.gz

# Verify dir is gone
ls $PAW_TEST_DIR/org/ 2>&1
# Expect: No such file or directory

# Inspect archive contents
tar -tzf ~/.pocketpaw/archives/org-destroyed-*.tar.gz | head -20
# Expect: journal.db, root.soul, keys/root.ed25519, etc.
```

### Pass/fail signals

| Signal | Pass | Fail |
|--------|------|------|
| Missing flags | refuses with non-zero | proceeds destructively |
| Wrong org name at prompt | refuses, dir intact | proceeds |
| Correct both flags + name | tarball created, dir wiped | one without the other |
| Archive contains full state | journal.db + root.soul + keys all present | missing files |

---

## Use Case 8 — Re-init on Same Dir

**Goal:** verify `--force` semantics and that a re-init produces a genuinely fresh org (new root DID, new genesis event).

### Steps

```bash
# After Use Case 7 the dir is destroyed. Re-init fresh.
uv run soul paw os init --data-dir $PAW_TEST_DIR --non-interactive \
  --org-name "Acme Take Two" --purpose "Round 2" \
  --values "caution" --founder-name "Alice" --founder-email "alice@acme.test" \
  --scopes "org:me" --fleet "Skip"

# Confirm it's a different org
uv run soul paw os status --data-dir $PAW_TEST_DIR
# Root DID should be different from the pre-destroy DID
# Event count starts from the new genesis
```

### Pass/fail signals

| Signal | Pass | Fail |
|--------|------|------|
| New org uses different DID | different from archived one | accidentally re-uses keys |
| Event count resets | low number (6–10) | inherited from archive |

---

## Quick-Check Matrix

A compressed "does everything work" run. ~5 minutes if you're fast.

```bash
# 1. Bootstrap
rm -rf /tmp/paw-q /tmp/paw-q-archive
uv run soul paw os init --data-dir /tmp/paw-q --non-interactive \
  --org-name Q --purpose Q --values "x" \
  --founder-name Q --founder-email q@q --scopes "org:q" --fleet "Skip"

# 2. Status
uv run soul paw os status --data-dir /tmp/paw-q | grep -q "^Org: Q" && echo "status OK"

# 3. Journal queryable
uv run python -c "
from soul_protocol.engine.journal import open_journal
from pathlib import Path
j = open_journal(Path('/tmp/paw-q/org/journal.db'))
events = j.query(limit=100)
assert len(events) > 0, 'no events'
assert any(e.action == 'org.created' for e in events), 'no genesis'
print(f'journal OK ({len(events)} events)')
"

# 4. Undeletability
uv run soul delete /tmp/paw-q/org/root.soul 2>&1 | grep -q -i "protect\|root" && echo "undeletable OK"

# 5. Destroy
uv run soul paw os destroy --data-dir /tmp/paw-q --confirm --i-mean-it --non-interactive --yes
ls /tmp/paw-q/org/ 2>/dev/null && echo "FAIL: dir survived" || echo "destroy OK"
```

If all five echo "OK", the v0.3 primitives are live and behaving.

---

## Known Gaps (v0.3 scope)

Things that are specced but not wired in this stack:

- **Soul-as-projection (Phase 2).** Soul memory tiers still write directly. `rebuild_from_journal()` not implemented yet.
- **Redirect existing stores (Phase 3).** Retrieval log, Fabric, kb-go still have their own write paths. The related PRs are currently on hold (see the audit in session memory).
- **Decision-trace wire-in.** Spec ships; the pocketpaw-side emit points (tool-call preview, draft approval UI) are a follow-up PR in that repo.
- **First concrete source adapter.** Retrieval router + broker infra is live. Google Drive adapter (C2) is the next concrete integration.
- **Signing mandatory.** `EventEntry.sig` is optional in v0.3; mandatory in v1.1.

If any of these trip you during testing, it's expected — flag in the usual channels.

---

*Last updated 2026-04-13 alongside docs/architecture.md v0.3 revisions.*
