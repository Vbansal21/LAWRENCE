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

if [ "$FAIL" -eq 0 ]; then
    echo "CHECK: PASS"
    exit 0
fi
echo "CHECK: FAIL ($FAIL step(s))"
exit 1
