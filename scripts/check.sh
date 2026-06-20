#!/usr/bin/env bash
# Master offline gate — every plan task runs this before AND after its change.
# No model/server needed. Exit 0 = good.
set -u
cd "$(dirname "$0")/.."

FAIL=0
step() {
    local name="$1"; shift
    if "$@" >/tmp/lk-check-step.log 2>&1; then
        echo "  OK    $name"
    else
        echo "  FAIL  $name"
        tail -20 /tmp/lk-check-step.log | sed 's/^/        /'
        FAIL=$((FAIL + 1))
    fi
}

echo "== LAWRENCE offline check =="
step "syntax (compileall)"  python3 -m compileall -q services/lk apps/desktop/scripts/ui_bridge.py
step "node syntax (web entrypoints)" bash -c 'command -v node >/dev/null && for f in apps/desktop/web/bootstrap.js apps/desktop/web/lib/bridge.js apps/desktop/web/variants/classic/app.js; do node --check "$f" || exit 1; done || echo "node not installed — skipped"'
step "offline suite"        python3 services/lk/tests/test_offline.py
step "edge suite"           python3 services/lk/tests/test_edge.py
step "concurrency suite"    python3 services/lk/tests/test_concurrency.py
step "context snapshot"     python3 services/lk/tests/test_context_snapshot.py
step "privacy policy"       python3 services/lk/tests/test_policy.py
step "confirmed agency"     python3 services/lk/tests/test_agency.py
step "memory-tier suite"    python3 services/lk/tests/test_memory_tiers.py
step "extraction suite"     python3 services/lk/tests/test_extract.py
step "zettelkasten suite"   python3 services/lk/tests/test_notes.py
step "chat/session suite"   python3 services/lk/tests/test_chats.py
step "chat-dag suite"       python3 services/lk/tests/test_chats_dag.py
step "chat-ops bridge suite" python3 services/lk/tests/test_chat_ops_bridge.py
step "chat-memory suite"    python3 services/lk/tests/test_chat_memory.py
step "autonomy retry"       python3 services/lk/tests/test_autonomy.py
step "cognitive-tick suite" python3 services/lk/tests/test_tick.py
step "significance suite"   python3 services/lk/tests/test_significance.py
step "slow-loop suite"      python3 services/lk/tests/test_refine.py
step "elevation suite"      python3 services/lk/tests/test_elevate.py
step "journal suite"        python3 services/lk/tests/test_journal.py
step "cancellation suite"   python3 services/lk/tests/test_cancel.py
step "capability suite"     python3 services/lk/tests/test_capabilities.py
step "proactive dedup"      python3 services/lk/tests/test_proactive_dedup.py
step "retrieval rank"       python3 services/lk/tests/test_retrieval_rank.py
step "embedding seam"       python3 services/lk/tests/test_embed.py
step "memory-recall suite"  python3 services/lk/tests/test_memory_index.py
step "retrieval-engine suite" python3 services/lk/tests/test_retrieval_engine.py
step "retrieval quality"    python3 services/lk/tests/test_retrieval_quality.py
step "schedule suite"       python3 services/lk/tests/test_schedule.py
step "converters suite"     python3 services/lk/tests/test_converters.py
step "service-registry suite" python3 services/lk/tests/test_services.py
step "turn-cache suite"     python3 services/lk/tests/test_turncache.py
step "bridge-race suite"    python3 services/lk/tests/test_bridge_races.py
step "backup/retention"     python3 services/lk/tests/test_backup.py
step "winhost (bloat fix)"  python3 services/lk/tests/test_winhost.py
step "notify/bloat suite"   python3 services/lk/tests/test_notify.py
step "recent-findings suite" python3 services/lk/tests/test_recent_findings.py
step "launcher suite"       python3 services/lk/tests/test_launcher.py
step "kernel stress"        python3 services/lk/tests/stress_kernel.py
step "memory stress"        python3 services/lk/tests/stress_memory.py
step "logs stress"          python3 services/lk/tests/stress_logs.py
step "journal stress"       python3 services/lk/tests/stress_journal.py
step "sensor stress"        python3 services/lk/tests/stress_sensors.py
step "ui-contract stress"   python3 services/lk/tests/stress_ui.py

if [ "$FAIL" -eq 0 ]; then
    echo "CHECK: PASS"
    exit 0
fi
echo "CHECK: FAIL ($FAIL step(s))"
exit 1
