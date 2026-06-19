"""Frozen context boundary: one run never mixes rolling-memory versions."""
import sys
sys.path.insert(0, "services")

from lk.kernel.invoke import freeze_context


class ChangingContext:
    def __init__(self):
        self.current = 1
        self.reads = 0

    def version(self):
        return self.current

    def tail_for_model(self):
        self.reads += 1
        if self.reads == 1:
            self.current += 1
        return f"context-v{self.current}"


ctx = ChangingContext()
snapshot = freeze_context(ctx)
assert snapshot.version == 2
assert snapshot.text == "context-v2"
assert ctx.reads == 2
print("CONTEXT SNAPSHOT: PASS")
