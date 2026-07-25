# Issue Contract — `anthropic-agent-coordinator`

## Pain
Multi-agent work needs capability-aware assignment under load.

## Claim
Coordinator assigns task to capable agent with capacity.

## Proof
```bash
python3 job-app/helix/proofs/proof_agent_coord.py
```

## Done when
Proof exits 0. Architecture (strand/integrity/helix) is **not** a substitute for this proof.

## Anti-claim
Not a full multi-agent platform.
