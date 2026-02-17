"""
Continuous agent runner.

This is the control loop that turns the orchestration engine into a running system.

Workflow per cycle
1) Load inventory from an InventoryPlugin
2) Fetch intents from an IntentSource
3) For each intent, run engine once
4) Print results and alerts
5) Sleep

This runner does not implement status tracking yet.
That is the next logical checkin.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from datacenter_orchestrator.agent.engine import OrchestrationEngine
from datacenter_orchestrator.intent.base import IntentSource
from datacenter_orchestrator.inventory.plugins.base import InventoryPlugin


@dataclass(frozen=True)
class RunnerConfig:
    """Runner configuration."""

    interval_seconds: int = 10


class AgentRunner:
    """
    Continuous runner.

    engine executes intents
    inventory_plugin loads device inventory
    intent_source fetches intent changes
    """

    def __init__(
        self,
        engine: OrchestrationEngine,
        inventory_plugin: InventoryPlugin,
        intent_source: IntentSource,
        config: RunnerConfig | None = None,
    ) -> None:
        self._engine = engine
        self._inventory_plugin = inventory_plugin
        self._intent_source = intent_source
        self._config = config or RunnerConfig()

    def run_forever(self) -> None:
        """Run the control loop forever."""
        while True:
            self.run_cycle()
            time.sleep(self._config.interval_seconds)

    def run_cycle(self) -> None:
        """
        Run a single cycle.

        We keep this separate to support unit tests and controlled runs.
        """
        inventory = self._inventory_plugin.load()
        intents = self._intent_source.fetch()

        if not intents:
            return

        for intent in intents:
            result = self._engine.run_once(intent, inventory)
            if result.ok:
                print(f"intent {intent.change_id} ok")
                continue

            alert = result.alert
            if alert is None:
                print(f"intent {intent.change_id} failed with unknown alert")
                continue

            print(f"intent {intent.change_id} failed severity {alert.severity}")
            print(alert.summary)
            for msg in alert.verification_failures:
                print(f"failure {msg}")
