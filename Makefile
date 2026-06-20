.PHONY: run lint test test-fast check llama-server mvp-smoke retrieval-smoke autonomy-smoke agency-smoke local-smoke kv-smoke unattended-smoke mvp-accept help

check:               ## full offline gate (syntax + all test suites) — plan tasks run this
	@bash scripts/check.sh

mvp-smoke:           ## start, exercise, and stop the cloud-first MVP runtime
	@python3 scripts/mvp_smoke.py

retrieval-smoke:     ## measure live memory, document, cached-web, and cold-web retrieval
	@python3 scripts/retrieval_smoke.py

autonomy-smoke:      ## run one live perception-to-finding cycle without a user turn
	@python3 scripts/autonomy_smoke.py

agency-smoke:        ## prove model proposal, confirmation, and one safe state change
	@python3 scripts/agency_smoke.py

llama-server:        ## rebuild the bundled local runtime
	@cmake --build third_party/llama.cpp/build --config Release -j"$$(nproc)" --target llama-server

local-smoke: llama-server ## prove core contracts against the bundled llama.cpp model
	@python3 scripts/local_compat_smoke.py

kv-smoke: llama-server ## prove local KV save and restore across a server restart
	@python3 scripts/kv_smoke.py

unattended-smoke:    ## run one real unattended hour with bounded cloud cadence
	@python3 scripts/unattended_smoke.py --seconds 3600

mvp-accept:          ## run the complete cloud/local MVP acceptance gate
	@$(MAKE) check
	@$(MAKE) mvp-smoke
	@$(MAKE) retrieval-smoke
	@$(MAKE) autonomy-smoke
	@$(MAKE) agency-smoke
	@$(MAKE) local-smoke
	@$(MAKE) kv-smoke
	@cd apps/desktop && npm run test:features && npm run test:runtime
	@cd apps/desktop/src-tauri && cargo check
	@$(MAKE) unattended-smoke

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
	'lk.ctx.store','lk.ctx.gate','lk.ctx.distill','lk.ctx.extract','lk.ctx.notes','lk.ctx.promote','lk.ctx.chats','lk.ctx.significance','lk.obs.vision','lk.obs.audio','lk.obs.spool', \
	'lk.retrieval.pipeline','lk.retrieval.db','lk.retrieval.vectors','lk.kernel.invoke','lk.kernel.tick','lk.kernel.refine','lk.kernel.elevate','lk.kernel.journal']; \
	[importlib.import_module(m) for m in mods]; print('import OK ('+str(len(mods))+' modules)')"

test: test-fast      ## full offline regression suite (no model/server needed)
	@python3 services/lk/tests/test_offline.py
	@python3 services/lk/tests/test_edge.py
	@python3 services/lk/tests/test_concurrency.py
	@python3 services/lk/tests/test_context_snapshot.py
	@python3 services/lk/tests/test_policy.py
	@python3 services/lk/tests/test_agency.py
	@python3 services/lk/tests/test_memory_tiers.py
	@python3 services/lk/tests/test_extract.py
	@python3 services/lk/tests/test_notes.py
	@python3 services/lk/tests/test_promote.py
	@python3 services/lk/tests/test_chats.py
	@python3 services/lk/tests/test_chats_dag.py
	@python3 services/lk/tests/test_chat_ops_bridge.py
	@python3 services/lk/tests/test_chat_memory.py
	@python3 services/lk/tests/test_autonomy.py
	@python3 services/lk/tests/test_tick.py
	@python3 services/lk/tests/test_significance.py
	@python3 services/lk/tests/test_refine.py
	@python3 services/lk/tests/test_elevate.py
	@python3 services/lk/tests/test_journal.py
	@python3 services/lk/tests/test_cancel.py
	@python3 services/lk/tests/test_capabilities.py
	@python3 services/lk/tests/test_proactive_dedup.py
	@python3 services/lk/tests/test_retrieval_rank.py
	@python3 services/lk/tests/test_embed.py
	@python3 services/lk/tests/test_memory_index.py
	@python3 services/lk/tests/test_retrieval_engine.py
	@python3 services/lk/tests/test_retrieval_quality.py
	@python3 services/lk/tests/test_schedule.py
	@python3 services/lk/tests/test_converters.py
	@python3 services/lk/tests/test_notify.py
	@python3 services/lk/tests/test_recent_findings.py
	@python3 services/lk/tests/test_launcher.py
	@python3 services/lk/tests/stress_kernel.py
	@python3 services/lk/tests/stress_memory.py
	@python3 services/lk/tests/stress_logs.py
	@python3 services/lk/tests/stress_journal.py
	@python3 services/lk/tests/stress_sensors.py
	@python3 services/lk/tests/test_voice_decode.py
	@python3 services/lk/tests/stress_ui.py
	@echo "ALL TESTS PASSED"
