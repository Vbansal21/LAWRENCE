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
step "node syntax (app.js)" bash -c 'command -v node >/dev/null && node --check apps/desktop/web/app.js || echo "node not installed — skipped"'
step "offline suite"        python3 services/lk/tests/test_offline.py
step "edge suite"           python3 services/lk/tests/test_edge.py
step "concurrency suite"    python3 services/lk/tests/test_concurrency.py
step "memory-tier suite"    python3 services/lk/tests/test_memory_tiers.py
step "extraction suite"     python3 services/lk/tests/test_extract.py
step "zettelkasten suite"   python3 services/lk/tests/test_notes.py
step "cognitive-tick suite" python3 services/lk/tests/test_tick.py
step "significance suite"   python3 services/lk/tests/test_significance.py
step "slow-loop suite"      python3 services/lk/tests/test_refine.py
step "elevation suite"      python3 services/lk/tests/test_elevate.py
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
