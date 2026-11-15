"""Pure advisory policies; no Store, filesystem, scheduler or provider access."""
from fractions import Fraction

from . import director_contract as C
from .study_json import digest, encode, sha


def recommend(observation_bytes, policy_bytes, *,
              expected_observation_sha256, expected_policy_sha256):
    """Return immutable canonical bytes, binding exact supplied input bytes.

    Digests do not authenticate permission. Caller pins the implementation
    separately and must recheck current admission before any future execution.
    """
    for raw, expected in ((observation_bytes, expected_observation_sha256),
                          (policy_bytes, expected_policy_sha256)):
        sha(expected)
        if type(raw) is not bytes or digest(raw) != expected:
            raise ValueError("frozen input digest mismatch")
    observed = C.observation(observation_bytes)
    policy = C.policy(policy_bytes)
    global_reasons = C.blockers(observed["gate"])
    eligible, excluded = [], []
    blocked_positive = False
    for row in observed["candidates"]:
        reasons = ["observation:" + r for r in global_reasons]
        reasons += ["candidate:" + r for r in C.blockers(row["gate"])]
        if row["declared_gain"] <= 0:
            reasons.append("nonpositive_declared_gain")
        if reasons:
            excluded.append({"candidate_id": row["candidate_id"], "reasons": reasons})
            blocked_positive |= row["declared_gain"] > 0
        else:
            eligible.append(row)
    policy_id = policy["policy_id"]
    if policy_id == "declared-gain-cost/v1":
        eligible.sort(key=lambda row: (
            -Fraction(row["declared_gain"], sum(row["declared_cost"].values())),
            row["candidate_id"]))
    elif policy_id == "seeded-hash-order/v1":
        eligible.sort(key=lambda row: (
            digest(encode({"seed": policy["seed"], "candidate_id": row["candidate_id"]})),
            row["candidate_id"]))
    selected = eligible[0] if eligible else None
    action = "recommend" if selected else "defer" if global_reasons or blocked_positive else "stop"
    reason = ("eligible_positive_declared_gain" if selected else
              "admission_recheck_required" if action == "defer" else
              "no_positive_declared_candidate")
    return encode({
        "schema": C.RECOMMENDATION, "mode": "shadow", "authority": "none",
        "execution_allowed": False, "requires_live_admission_recheck": True,
        "observation_sha256": expected_observation_sha256,
        "policy_sha256": expected_policy_sha256, "policy_id": policy_id,
        "action": action, "reason": reason,
        "selected_candidate_id": selected["candidate_id"] if selected else None,
        "selected_task_sha256": selected["task_sha256"] if selected else None,
        "ranked_candidate_ids": [row["candidate_id"] for row in eligible],
        "excluded": excluded, "observation_blockers": global_reasons,
        "score_semantics": "declared_hypothetical_not_calibrated_or_scientific",
    })
