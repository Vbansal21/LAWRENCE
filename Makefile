.PHONY: run lint test test-fast help

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
	'lk.ctx.store','lk.ctx.gate','lk.ctx.distill','lk.obs.vision','lk.obs.audio','lk.obs.spool', \
	'lk.retrieval.pipeline','lk.retrieval.db','lk.kernel.invoke']; \
	[importlib.import_module(m) for m in mods]; print('import OK ('+str(len(mods))+' modules)')"

test: test-fast      ## full offline regression suite (no model/server needed)
	@python3 services/lk/tests/test_offline.py
	@python3 services/lk/tests/test_edge.py
	@python3 services/lk/tests/test_concurrency.py
	@echo "ALL TESTS PASSED"
