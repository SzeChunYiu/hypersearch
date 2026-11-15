"""Closed shadow declarations; integer units are supplied hypotheses."""
from .study_json import fields, integer, parse, sha, text

OBSERVATION = "hypersearch.director-observation/v1"
POLICY = "hypersearch.director-policy/v1"
RECOMMENDATION = "hypersearch.director-recommendation/v1"
POLICIES = ("supplied-order/v1", "declared-gain-cost/v1", "seeded-hash-order/v1")
COSTS = ("execution", "verification", "coordination", "recovery")


def choice(value, options):
    if type(value) is not str or value not in options:
        raise ValueError("unknown closed vocabulary value")


def gate(value):
    fields(value, "permission hold dependency")
    choice(value["permission"], ("allowed", "pending", "denied", "revoked"))
    choice(value["hold"], ("clear", "active"))
    choice(value["dependency"], ("ready", "pending", "revoked"))


def blockers(value):
    reasons = []
    if value["permission"] != "allowed":
        reasons.append("permission:" + value["permission"])
    if value["hold"] != "clear":
        reasons.append("hold:active")
    if value["dependency"] != "ready":
        reasons.append("dependency:" + value["dependency"])
    return reasons


def observation(raw):
    value = parse(raw)
    fields(value, "schema observation_id consumer_commit gain_unit cost_unit gate candidates")
    choice(value["schema"], (OBSERVATION,))
    for key in ("observation_id", "gain_unit", "cost_unit"):
        text(value[key])
    sha(value["consumer_commit"], 40)
    gate(value["gate"])
    rows = value["candidates"]
    if type(rows) is not list or len(rows) > 1000:
        raise ValueError("candidates must be a bounded array")
    seen = set()
    tasks = set()
    for row in rows:
        fields(row, "candidate_id task_sha256 declared_gain declared_cost gate")
        text(row["candidate_id"])
        if row["candidate_id"] in seen:
            raise ValueError("duplicate candidate identity")
        seen.add(row["candidate_id"])
        sha(row["task_sha256"])
        if row["task_sha256"] in tasks:
            raise ValueError("duplicate frozen task identity")
        tasks.add(row["task_sha256"])
        integer(row["declared_gain"], -(10**12), 10**12)
        fields(row["declared_cost"], " ".join(COSTS))
        for cost in row["declared_cost"].values():
            integer(cost, 0, 10**12)
        if sum(row["declared_cost"].values()) <= 0:
            raise ValueError("declared total cost must be positive")
        gate(row["gate"])
    return value


def policy(raw):
    value = parse(raw)
    fields(value, "schema policy_id seed")
    choice(value["schema"], (POLICY,))
    choice(value["policy_id"], POLICIES)
    integer(value["seed"], 0, 2**64 - 1)
    if value["policy_id"] != "seeded-hash-order/v1" and value["seed"] != 0:
        raise ValueError("unused seed must be zero")
    return value
