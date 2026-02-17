"""
Verification engine.

Purpose
After config is applied, we must compare observed state to desired state.
This module evaluates a VerificationSpec against observed device state.

Observed state format
observed_state is a dict:
  device name -> dict of model path -> value

This mirrors the model_paths structure in ChangeAction and keeps verification simple.

Extensibility
Later you can add:
- protocol checks based on OpenConfig telemetry
- active probes like ping and tcp connect
- convergence windows and retry logic
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from datacenter_orchestrator.core.types import VerificationSpec


@dataclass
class VerificationOutcome:
    """
    Verification outcome.

    ok
    True only when every check passes.

    failures
    List of human readable failure messages.

    evidence
    Structured evidence that can be attached to alerts.
    """

    ok: bool
    failures: list[str]
    evidence: dict[str, object]


def evaluate_verification(
    spec: VerificationSpec,
    observed_state: dict[str, dict[str, Any]],
) -> VerificationOutcome:
    """
    Evaluate a VerificationSpec.

    Supported check types
    path_equals
    - device: str
    - path: str
    - expected: Any
    """

    failures: list[str] = []
    evidence: dict[str, object] = {"check_results": []}

    for idx, check in enumerate(spec.checks):
        ctype = str(check.get("type", ""))

        if ctype != "path_equals":
            failures.append(f"unsupported check type at index {idx}: {ctype}")
            evidence["check_results"].append(
                {"index": idx, "type": ctype, "ok": False, "reason": "unsupported"}
            )
            continue

        device = str(check.get("device", ""))
        path = str(check.get("path", ""))
        expected = check.get("expected")

        device_state = observed_state.get(device, {})
        if path not in device_state:
            failures.append(f"missing observed path for device {device}: {path}")
            evidence["check_results"].append(
                {
                    "index": idx,
                    "type": ctype,
                    "device": device,
                    "path": path,
                    "ok": False,
                    "reason": "missing",
                }
            )
            continue

        observed = device_state.get(path)
        if observed != expected:
            failures.append(
                f"value mismatch device {device} path {path} expected {expected} observed {observed}"
            )
            evidence["check_results"].append(
                {
                    "index": idx,
                    "type": ctype,
                    "device": device,
                    "path": path,
                    "ok": False,
                    "expected": expected,
                    "observed": observed,
                }
            )
            continue

        evidence["check_results"].append(
            {"index": idx, "type": ctype, "device": device, "path": path, "ok": True}
        )

    ok = len(failures) == 0
    return VerificationOutcome(ok=ok, failures=failures, evidence=evidence)
