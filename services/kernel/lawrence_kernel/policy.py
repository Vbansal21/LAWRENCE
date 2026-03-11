from __future__ import annotations

from dataclasses import dataclass

from lawrence_kernel.config import PolicyConfig, RoutingConfig
from lawrence_kernel.models import TurnContextSnapshot, TurnInput


@dataclass
class PolicyDecision:
    allow_web: bool
    allow_tools: bool
    allow_cloud: bool


class PolicyEngine:
    def __init__(self, policy: PolicyConfig, routing: RoutingConfig) -> None:
        self._policy = policy
        self._routing = routing

    def evaluate_turn(self, turn: TurnInput, snapshot: TurnContextSnapshot) -> PolicyDecision:
        query = (turn.user_query or "").lower()
        explicit_web = "web" in query or "search" in query or turn.force_web
        allow_web = self._routing.web_parallel_default or explicit_web
        allow_tools = True
        allow_cloud = self._policy.allow_cloud_default

        # Block unsafe tools by default if query appears destructive.
        if "delete" in query or "reset" in query:
            allow_tools = False

        snapshot.policy_state = {
            "telemetry_enabled": self._policy.telemetry_enabled,
            "require_confirmation_for_actions": self._policy.require_confirmation_for_actions,
            "allow_cloud": allow_cloud,
            "allow_web": allow_web,
            "allow_tools": allow_tools,
        }
        return PolicyDecision(allow_web=allow_web, allow_tools=allow_tools, allow_cloud=allow_cloud)
