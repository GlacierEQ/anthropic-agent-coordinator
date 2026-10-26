"""Reissue machine/promotion_authority.json via the repo's own promotion authority.

The machine grant is a short-lived HMAC grant (see src/promotion_authority.py).
It binds the current machine/proof_receipt.json digest + source_sha and expires
after its TTL, so it must be reissued when it lapses. This script performs the
reissue through PromotionAuthority with the documented local operator secret —
it never hand-edits the expiry or forges a MAC. It preserves the grant file's
other fields (repository, source_sha, proof_receipt_digest, issuer, verified,
secret_ref) and only refreshes not_after + mac.

Original issuance used a 30-day TTL (2026-08-10 -> 2026-09-09); this script
keeps that same TTL so the reissue matches the established issuance parameters.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.promotion_authority import LOCAL_OPERATOR_SECRET, PromotionAuthority  # noqa: E402

GRANT_PATH = ROOT / "machine" / "promotion_authority.json"
PROOF_PATH = ROOT / "machine" / "proof_receipt.json"

# TTL matching the original machine-grant issuance (30 days).
GRANT_TTL_S = 30 * 24 * 60 * 60


def main() -> int:
    grant = json.loads(GRANT_PATH.read_text(encoding="utf-8"))
    proof_bytes = PROOF_PATH.read_bytes()
    proof = json.loads(proof_bytes.decode("utf-8"))

    file_digest = hashlib.sha256(proof_bytes).hexdigest()
    if grant["proof_receipt_digest"] != file_digest:
        raise SystemExit(
            "refusing to reissue: grant proof_receipt_digest no longer matches proof receipt"
        )
    if grant["source_sha"] != proof["source_sha"]:
        raise SystemExit("refusing to reissue: grant source_sha no longer matches proof receipt")

    authority = PromotionAuthority(LOCAL_OPERATOR_SECRET, ttl_s=GRANT_TTL_S)
    issued = authority.issue(
        grant["repository"],
        grant["source_sha"],
        grant["proof_receipt_digest"],
    )
    ok, reason = authority.verify(issued)
    if not ok:
        raise SystemExit(f"freshly issued grant failed verification: {reason}")

    grant["not_after"] = issued.not_after
    grant["mac"] = issued.mac
    # Preserve the file's original key order; only not_after + mac change.
    GRANT_PATH.write_text(json.dumps(grant, indent=2) + "\n", encoding="utf-8")
    print(f"reissued {GRANT_PATH} (not_after={issued.not_after}, ttl_s={GRANT_TTL_S})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
