from __future__ import annotations

import json

from scripts import operate


def test_operate_preserves_constrained_plan_as_continuation_work():
    receipt = operate.operate()

    assert receipt["continuation"] == "enabled"
    assert receipt["status"] == "observed"
    assert receipt["smoke"]["kind"] == "continuation_scheduler"
    assert any(item.startswith("constrained:continue_task:plan:reason:global_budget") for item in receipt["resolution_work"])
    assert any(item.startswith("constrained:continue_task:implement:reason:dependency_not_completed") for item in receipt["resolution_work"])


def test_main_emits_resolution_receipt_and_success_exit(monkeypatch, capsys):
    def broken() -> dict[str, object]:
        raise RuntimeError("simulated")

    monkeypatch.setattr(operate, "operate", broken)

    assert operate.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["continuation"] == "enabled"
    assert payload["status"] == "resolution_required"
    assert payload["resolution_work"] == ["inspect_operation_runtime:RuntimeError"]
