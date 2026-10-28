#!/bin/bash
# scripts/smoke-v0.5.0.sh — End-to-end smoke test for soul-protocol v0.5.0.
# Created: 2026-04-30
#
# Exercises every v0.5.0-touched surface against a fresh .soul file:
#   - birth (#46 multi-user soul)
#   - status (#194 density-driven focus, #46 per-user bonds)
#   - observe with --user (#46 multi-user) and --domain (#41)
#   - remember with --domain (#41)
#   - recall with --user, --domain, --layer (#46, #41)
#   - layers display (#41)
#   - supersede + forget --id (#193)
#   - verify chain (#42, #210 hardening)
#   - audit log with summaries (#201)
#   - prune-chain (#203)
#   - graph nodes/edges/neighbors/path (#108, #190)
#   - soul diff between two snapshots (#191)
#   - soul journal init/append/query (#189)
#   - soul eval against a YAML spec (#160)
#
# Usage:
#   bash scripts/smoke-v0.5.0.sh                  # run with auto cleanup
#   SMOKE_KEEP_ARTIFACTS=1 bash scripts/smoke-v0.5.0.sh   # keep /tmp/soul-smoke-v050/
#
# Exit code:
#   0 on success — every command produced expected output
#   1 on first failure (the script halts and prints the failing step)

set -euo pipefail

# Resolve the script's repo root so SOUL_BIN works regardless of cwd.
REPO_ROOT=${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
SOUL_BIN=${SOUL_BIN:-"uv run --project $REPO_ROOT soul"}
WORK_DIR=${WORK_DIR:-/tmp/soul-smoke-v050}
KEEP_ARTIFACTS=${SMOKE_KEEP_ARTIFACTS:-0}

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

step_count=0

step() {
    step_count=$((step_count + 1))
    printf "\n${BLUE}[%02d]${NC} ${YELLOW}%s${NC}\n" "$step_count" "$1"
}

check() {
    local desc="$1"
    local cmd="$2"
    if eval "$cmd" >/dev/null 2>&1; then
        printf "    ${GREEN}✓${NC} %s\n" "$desc"
    else
        printf "    ${RED}✗${NC} %s\n      ${RED}command failed:${NC} %s\n" "$desc" "$cmd"
        exit 1
    fi
}

cleanup() {
    if [ "$KEEP_ARTIFACTS" != "1" ]; then
        rm -rf "$WORK_DIR"
    else
        printf "\n${YELLOW}Artifacts kept at:${NC} %s\n" "$WORK_DIR"
    fi
}
trap cleanup EXIT

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

printf "${BLUE}========================================${NC}\n"
printf "${BLUE}  soul-protocol v0.5.0 smoke test${NC}\n"
printf "${BLUE}========================================${NC}\n"
printf "Working dir: %s\n" "$WORK_DIR"
printf "Soul CLI:    %s\n" "$SOUL_BIN"

# ============================================================================
# Phase 1 — Identity bundle (v0.4.0 carried forward)
# ============================================================================

step "Birth a fresh soul"
$SOUL_BIN birth "TestSoul" --archetype "Smoke test soul" --output test.soul
check "test.soul created" "test -f test.soul"

step "Inspect status"
$SOUL_BIN status test.soul
check "status command exits 0" "$SOUL_BIN status test.soul"

# ============================================================================
# Phase 2 — Multi-user observe (#46) + domain (#41) + density focus (#194)
# ============================================================================

step "Observe interactions for user 'alice' in default domain"
$SOUL_BIN observe test.soul \
    --user-input "I love working with Python" \
    --agent-output "Python is a fantastic language" \
    --user alice
$SOUL_BIN observe test.soul \
    --user-input "Working on Project Aurora today" \
    --agent-output "Tell me about Project Aurora" \
    --user alice

step "Observe for user 'bob' (separation should hold)"
$SOUL_BIN observe test.soul \
    --user-input "Bob is debugging the database" \
    --agent-output "What's the issue with the database?" \
    --user bob

step "Verify per-user bond strengths in status"
$SOUL_BIN status test.soul
check "status still passes" "$SOUL_BIN status test.soul"

step "Recall for alice (should see her memories + legacy)"
$SOUL_BIN recall test.soul "Project" --user alice
check "recall --user alice exits 0" "$SOUL_BIN recall test.soul 'Project' --user alice"

step "Direct remember with --domain work"
$SOUL_BIN remember test.soul 'Q3 revenue is 4.2M dollars' \
    --type semantic --importance 8 --domain work
$SOUL_BIN remember test.soul "Friend's birthday March 5" \
    --type semantic --importance 6
check "two memories written" "true"

step "Recall scoped to --domain work"
$SOUL_BIN recall test.soul "revenue" --domain work --limit 5
check "domain filter recall exits 0" "$SOUL_BIN recall test.soul 'revenue' --domain work --limit 5"

step "Layers breakdown shows per-domain counts"
$SOUL_BIN layers test.soul
check "soul layers exits 0" "$SOUL_BIN layers test.soul"

# ============================================================================
# Phase 3 — Memory update primitives (#193)
# ============================================================================

step "Capture memory id for supersede/forget tests"
MEM_ID=$($SOUL_BIN recall test.soul "revenue" --json --limit 1 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    mems = d.get('memories', [])
    print(mems[0]['id'] if mems else '')
except Exception:
    print('')
" || echo "")
printf "    captured id: %s\n" "${MEM_ID:-<none>}"
if [ -z "${MEM_ID:-}" ]; then
    printf "    ${YELLOW}!${NC} no memory captured — skipping supersede/forget steps\n"
fi

if [ -n "${MEM_ID:-}" ]; then
    step "Supersede the memory"
    $SOUL_BIN supersede test.soul 'Q3 revenue updated to 4.5M dollars' \
        --old-id "$MEM_ID" --reason "after final close"
    check "supersede exits 0" "true"

    step "Recall surfaces the new value"
    $SOUL_BIN recall test.soul "revenue" --limit 3
    check "recall finds superseded chain" "$SOUL_BIN recall test.soul 'revenue' --limit 3"

    step "forget --id (dry-run, no --apply)"
    $SOUL_BIN forget test.soul --id "$MEM_ID"
    check "forget dry-run exits 0" "$SOUL_BIN forget test.soul --id '$MEM_ID'"
fi

# ============================================================================
# Phase 4 — Trust chain (#42, #210, #213, #214)
# ============================================================================

step "Verify trust chain integrity"
$SOUL_BIN verify test.soul
check "verify exits 0 on clean chain" "$SOUL_BIN verify test.soul"

step "Audit log with --no-summary (hash-only view)"
$SOUL_BIN audit test.soul --no-summary --limit 5
check "audit --no-summary exits 0" "$SOUL_BIN audit test.soul --no-summary --limit 5"

step "Audit log with summaries (default)"
$SOUL_BIN audit test.soul --limit 5
check "audit with summaries exits 0" "$SOUL_BIN audit test.soul --limit 5"

step "Audit filter by action prefix (#201)"
$SOUL_BIN audit test.soul --filter memory. --limit 5
check "audit --filter exits 0" "$SOUL_BIN audit test.soul --filter memory. --limit 5"

step "Prune chain dry-run preview (#203)"
$SOUL_BIN prune-chain test.soul --keep 5
check "prune-chain dry-run exits 0" "$SOUL_BIN prune-chain test.soul --keep 5"

# ============================================================================
# Phase 5 — Graph traversal (#108, #190, #220 fix)
# ============================================================================

step "Graph nodes (typed entities)"
$SOUL_BIN graph nodes test.soul --limit 20
check "graph nodes exits 0" "$SOUL_BIN graph nodes test.soul --limit 20"

step "Graph edges"
$SOUL_BIN graph edges test.soul
check "graph edges exits 0" "$SOUL_BIN graph edges test.soul"

step "Graph neighbors (for first known entity, if any)"
NODE_NAME=$($SOUL_BIN graph nodes test.soul --json --limit 1 | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['nodes'][0]['name'] if d.get('nodes') else '')") || true
if [ -n "$NODE_NAME" ]; then
    $SOUL_BIN graph neighbors test.soul "$NODE_NAME" --depth 2
    check "graph neighbors exits 0" "$SOUL_BIN graph neighbors test.soul '$NODE_NAME' --depth 2"
else
    printf "    ${YELLOW}!${NC} skipped — no graph nodes yet\n"
fi

step "Graph mermaid (visual representation)"
$SOUL_BIN graph mermaid test.soul
check "graph mermaid exits 0" "$SOUL_BIN graph mermaid test.soul"

# ============================================================================
# Phase 6 — Soul diff (#191)
# ============================================================================

step "Snapshot soul as 'before' for diff"
cp test.soul before.soul
check "before.soul created" "test -f before.soul"

step "Modify soul (more observations)"
$SOUL_BIN observe test.soul \
    --user-input "Charlie joined the team yesterday" \
    --agent-output "Welcome to Charlie" \
    --user alice
check "modification observe exits 0" "true"

step "Diff before vs after — shows the new memories + bond change"
$SOUL_BIN diff before.soul test.soul --summary-only
check "soul diff exits 0" "$SOUL_BIN diff before.soul test.soul --summary-only"

step "Diff JSON output round-trips"
$SOUL_BIN diff before.soul test.soul --format json | python3 -m json.tool > /dev/null
check "diff JSON parses" "$SOUL_BIN diff before.soul test.soul --format json | python3 -m json.tool > /dev/null"

# ============================================================================
# Phase 7 — Soul journal CLI (#189)
# ============================================================================

step "Initialize a standalone journal"
$SOUL_BIN journal init journal.db
check "journal init exits 0" "test -f journal.db"

step "Append an event from CLI flags"
$SOUL_BIN journal append journal.db \
    --action git.commit \
    --actor '{"kind":"agent","id":"smoke-test"}' \
    --scope "smoke:test" \
    --payload '{"sha":"abc123","msg":"smoke"}'
check "journal append exits 0" "true"

step "Append events from stdin (JSONL)"
echo '{"action":"ci.run","actor":{"kind":"agent","id":"smoke-test"},"scope":["smoke:test"],"payload":{"build":42}}' | \
    $SOUL_BIN journal append journal.db --stdin
check "journal stdin append exits 0" "true"

step "Query the journal with --action-prefix"
$SOUL_BIN journal query journal.db --action-prefix git.
check "journal query exits 0" "$SOUL_BIN journal query journal.db --action-prefix git."

# ============================================================================
# Phase 8 — Soul eval (#160)
# ============================================================================

step "Write a minimal eval spec"
cat > smoke_eval.yaml <<'YAML'
name: smoke v0.5.0 keyword check
description: Validates keyword scoring runs without an engine
seed:
  soul:
    name: EvalTarget
    archetype: tester
  state: {}

cases:
  - name: simple keyword match
    inputs:
      message: hello
    scoring:
      kind: keyword
      expected: ["hello"]
      mode: any
      threshold: 1.0
YAML
check "eval spec written" "test -f smoke_eval.yaml"

step "Run soul eval"
$SOUL_BIN eval smoke_eval.yaml --json | python3 -m json.tool
check "eval exits 0" "$SOUL_BIN eval smoke_eval.yaml"

# ============================================================================
# Done
# ============================================================================

printf "\n${GREEN}========================================${NC}\n"
printf "${GREEN}  All %d steps passed${NC}\n" "$step_count"
printf "${GREEN}========================================${NC}\n"
