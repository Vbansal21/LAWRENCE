.PHONY: run lint test test-fast check help

check:               ## full offline gate (syntax + all test suites) — plan tasks run this
	@bash scripts/check.sh

help:                ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n", $$1, $$2}'

run:                 ## start LAWRENCE (CLI + observers; reuses a warm server if one is up)
	python3 lk.py

lint:                ## byte-compile every kernel source (fast syntax check)
	python3 -m compileall -q services/lk

test-fast:           ## import-check every module (catches import/wiring errors)
	@python3 -c "import sys; sys.path.insert(0,'services'); import importlib; \
	mods=['lk.cli','lk.sensor','lk.server','lk.profile','lk.model','lk.admin','lk.logger', \
	'lk.ctx.store','lk.ctx.gate','lk.ctx.distill','lk.ctx.extract','lk.ctx.notes','lk.ctx.chats','lk.ctx.significance','lk.obs.vision','lk.obs.audio','lk.obs.spool', \
	'lk.retrieval.pipeline','lk.retrieval.db','lk.kernel.invoke','lk.kernel.tick','lk.kernel.refine','lk.kernel.elevate','lk.kernel.journal']; \
	[importlib.import_module(m) for m in mods]; print('import OK ('+str(len(mods))+' modules)')"

test: test-fast      ## full offline regression suite (no model/server needed)
	@python3 services/lk/tests/test_offline.py
	@python3 services/lk/tests/test_edge.py
	@python3 services/lk/tests/test_concurrency.py
	@python3 services/lk/tests/test_memory_tiers.py
	@python3 services/lk/tests/test_extract.py
	@python3 services/lk/tests/test_notes.py
	@python3 services/lk/tests/test_chats.py
	@python3 services/lk/tests/test_chat_memory.py
	@python3 services/lk/tests/test_tick.py
	@python3 services/lk/tests/test_significance.py
	@python3 services/lk/tests/test_refine.py
	@python3 services/lk/tests/test_elevate.py
	@python3 services/lk/tests/test_journal.py
	@python3 services/lk/tests/stress_kernel.py
	@python3 services/lk/tests/stress_memory.py
	@python3 services/lk/tests/stress_logs.py
	@python3 services/lk/tests/stress_journal.py
	@python3 services/lk/tests/stress_sensors.py
	@python3 services/lk/tests/stress_ui.py
	@echo "ALL TESTS PASSED"
