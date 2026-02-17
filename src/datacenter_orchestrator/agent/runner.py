"""
Agent runner.

Purpose
Continuously:
- Load inventory
- Load intents
- Run orchestration engine

This is the composition layer of the system.
It wires planner, executor, guard, and optional MCP tooling.

Core engine remains pure.
Runner handles environment configuration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from datacenter_orchestrator.agent.engine import OrchestrationEngine
from datacenter_orchestrator.agent.mcp_client import MCPClient
from datacenter_orchestrator.execution.base import PlanExecutor
from datacenter_orchestrator.intent.base import IntentSource
from datacenter_orchestrator.inventory.plugins.base import InventoryPlugin
from datacenter_orchestrator.planner.planner import DeterministicPlanner


@dataclass(frozen=True)
class RunnerConfig:
    """
    Runner configuration.

    interval_seconds
    Sleep duration between cycles.

    use_mcp
    Enable MCP plan evaluation.

    mcp_url
    URL of MCP server.
    """

    interval_seconds: int = 10
    use_mcp: bool = False
    mcp_url: str = "http://127.0.0.1:8085"


class AgentRunner:
    """
    Top level orchestration loop.

    This is not the orchestration engine.
    This is the runtime loop.
    """

    def __init__(
        self,
        executor: PlanExecutor,
        inventory_plugin: InventoryPlugin,
        intent_source: IntentSource,
        config: RunnerConfig | None = None,
    ) -> None:
        self._config = config or RunnerConfig()
        self._executor = executor
        self._inventory_plugin = inventory_plugin
        self._intent_source = intent_source

        planner = DeterministicPlanner()

        evaluation_tool = None
        if self._config.use_mcp:
            evaluation_tool = MCPClient(base_url=self._config.mcp_url)

        self._engine = OrchestrationEngine(
            planner=planner,
            executor=self._executor,
            evaluation_tool=evaluation_tool,
        )

    def run_cycle(self) -> None:
        """
        Execute one orchestration cycle.
        """

        inventory = self._inventory_plugin.load()
        intents = self._intent_source.load()

        for intent in intents:
            result = self._engine.run_once(intent, inventory)

            if not result.ok and result.alert:
                print("ALERT:", result.alert.summary)
                print("Risk:", result.risk)

    def run_forever(self) -> None:
        """
        Continuous loop execution.
        """

        while True:
            self.run_cycle()
            time.sleep(self._config.interval_seconds)
