# Active MCP Plan (2026-03-10)

Target first MCP integrations for v0.1:
- filesystem read/search tools (policy-gated)
- browser research tool (policy + domain constraints)
- calendar tool deferred post-v0.1

Operational constraints:
- all tool execution requires explicit policy check
- medium/high risk actions require user confirmation
- execution logs must include `tool`, `args`, `policy_basis`, `outcome`
