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
    legal, excluded = [], []
    for row in observed["candidates"]:
        reasons = ["observation:" + r for r in global_reasons]
        reasons += ["candidate:" + r for r in C.blockers(row["gate"])]
        if reasons:
            excluded.append({"candidate_id": row["candidate_id"], "reasons": reasons})
        else:
            legal.append(row)
    policy_id = policy["policy_id"]
    eligible = list(legal)
    policy_skipped = []
    if policy_id == "declared-gain-cost/v1":
        eligible = [row for row in legal if row["declared_gain"] > 0]
        policy_skipped = [{"candidate_id": row["candidate_id"],
                           "reason": "greedy_nonpositive_declared_gain"}
                          for row in legal if row["declared_gain"] <= 0]
        eligible.sort(key=lambda row: (
            -Fraction(row["declared_gain"], sum(row["declared_cost"].values())),
            row["candidate_id"]))
    elif policy_id == "seeded-hash-order/v1":
        eligible.sort(key=lambda row: (
            digest(encode({"seed": policy["seed"], "candidate_id": row["candidate_id"]})),
            row["candidate_id"]))
    selected = eligible[0] if eligible else None
    action = "recommend" if selected else "defer" if global_reasons or (not legal and excluded) else "stop"
    reason = ("legal_candidate_selected_by_policy" if selected else
              "admission_recheck_required" if action == "defer" else
              "no_candidate_selected_by_policy")
    return encode({
        "schema": C.RECOMMENDATION, "mode": "shadow", "authority": "none",
        "execution_allowed": False, "requires_live_admission_recheck": True,
        "observation_sha256": expected_observation_sha256,
        "policy_sha256": expected_policy_sha256, "policy_id": policy_id,
        "action": action, "reason": reason,
        "selected_candidate_id": selected["candidate_id"] if selected else None,
        "selected_task_sha256": selected["task_sha256"] if selected else None,
        "legal_candidate_ids": [row["candidate_id"] for row in legal],
        "policy_skipped": policy_skipped,
        "ranked_candidate_ids": [row["candidate_id"] for row in eligible],
        "excluded": excluded, "observation_blockers": global_reasons,
        "score_semantics": "declared_hypothetical_not_calibrated_or_scientific",
    })
