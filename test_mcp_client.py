from datacenter_orchestrator.agent.mcp_client import MCPClient
from datacenter_orchestrator.core.types import (
    ChangeAction,
    ChangePlan,
    RollbackSpec,
    VerificationSpec,
)
from datacenter_orchestrator.inventory.store import InventoryStore
from datacenter_orchestrator.mcp.security import McpAuthConfig


def main() -> None:
    client = MCPClient(
        base_url="http://localhost:8080",
        auth=McpAuthConfig(
            auth_token="change_me",
            hmac_secret="change_me_too",
            allowed_clock_skew_seconds=60,
        ),
        timeout_seconds=5,
    )

    plan = ChangePlan(
        plan_id="test-plan-1",
        actions=[
            ChangeAction(
                device="leaf-01",
                model_paths={
                    "interfaces/interface[name=Ethernet1]/config/enabled": True,
                },
                reason="test action for standalone mcp server",
            )
        ],
        verification=VerificationSpec(
            checks=[
                {"type": "state_check", "target": "leaf-01", "expect": "reachable"},
            ],
            probes=[
                {"type": "ping", "target": "leaf-01"},
            ],
            window_seconds=60,
        ),
        rollback=RollbackSpec(
            enabled=True,
            triggers=["verification_failed"],
        ),
        risk="high",
        explanation="test plan for validating mcp client to server flow",
    )

    inventory = InventoryStore()

    try:
        result = client.evaluate_plan(
            plan=plan,
            inventory=inventory,
        )
        print("MCP call succeeded")
        print(result)
    except Exception as exc:
        print("MCP call failed")
        print(type(exc).__name__, str(exc))

        try:
            from urllib.error import HTTPError
            if isinstance(exc, HTTPError):
                body = exc.read().decode("utf-8")
                print("HTTP error body:")
                print(body)
        except Exception as inner_exc:
            print("Could not read error body:", inner_exc)

if __name__ == "__main__":
    main()
