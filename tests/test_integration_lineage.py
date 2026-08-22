from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINEAGE = json.loads(
    (ROOT / "machine" / "integration-lineage.json").read_text(encoding="utf-8")
)


def test_integration_lineage_pins_exact_donor_set() -> None:
    assert LINEAGE["schema"] == "glaciereq.integration-lineage.v1"
    assert LINEAGE["repository"] == "GlacierEQ/anthropic-agent-coordinator"
    expected = {
        "GlacierEQ/pro-code",
        "GlacierEQ/Pro_Code",
        "GlacierEQ/glaciereq-excellence-core",
        "GlacierEQ/apex-control-plane",
        "GlacierEQ/public-actions-runner-host",
    }
    assert {row["source_repo"] for row in LINEAGE["adoptions"]} == expected


def test_every_adoption_has_pinned_source_and_real_local_evidence() -> None:
    for adoption in LINEAGE["adoptions"]:
        assert len(adoption["source_blob_sha"]) == 40
        assert adoption["adopted_mechanisms"]
        assert adoption["local_evidence"]
        for path in adoption["local_evidence"]:
            assert (ROOT / path).exists(), f"missing local integration evidence: {path}"


def test_integration_preserves_strong_coordinator_instead_of_replacing_it() -> None:
    preserved = LINEAGE["preserved_local_mechanism"]
    assert preserved["source"] == "src/anthropic_agent_coordinator/coordinator.py"
    assert "reason_not_replaced" in preserved
    assert (ROOT / preserved["source"]).exists()


def test_lineage_does_not_claim_company_or_live_donor_connectivity() -> None:
    nonclaims = " ".join(LINEAGE["nonclaims"]).casefold()
    assert "anthropic affiliation" in nonclaims
    assert "live runtime connectivity" in nonclaims
