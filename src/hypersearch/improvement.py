"""Pure finite-suite comparison; it has no execution or promotion authority."""
from pathlib import Path

from .study_json import digest, encode, fields, integer, parse, sha, text

PLAN = "hypersearch.improvement-plan/v1"
RUN = "hypersearch.improvement-run/v1"
EVALUATION = "hypersearch.improvement-evaluation/v1"
EVALUATOR = "hypersearch.finite-suite-comparison/v1"
OUTCOMES = ("ACCEPT", "REJECT")
CASE_STATUSES = ("COMPLETED", "FAILED", "TIMEOUT", "NOT_RUN")
RUN_STATUSES = ("COMPLETE", "INCOMPLETE", "TIMEOUT", "UNKNOWN_COST")


def evaluator_source_sha256():
    """Identify the two local source files that implement the evaluator."""
    root = Path(__file__).resolve().parent
    sources = {name: digest((root / name).read_bytes())
               for name in ("improvement.py", "study_json.py")}
    return digest(encode(sources))


def _choice(value, options):
    if type(value) is not str or value not in options:
        raise ValueError("unknown closed vocabulary value")


def _source(value):
    fields(value, "id source_sha256")
    text(value["id"])
    sha(value["source_sha256"])


def _plan(raw):
    value = parse(raw)
    fields(value, "schema evaluator baseline candidate suite budget minimum_correct_weight_gain")
    _choice(value["schema"], (PLAN,))
    _source(value["evaluator"])
    if value["evaluator"]["id"] != EVALUATOR:
        raise ValueError("unsupported frozen evaluator")
    if value["evaluator"]["source_sha256"] != evaluator_source_sha256():
        raise ValueError("evaluator source bundle mismatch")
    _source(value["baseline"])
    _source(value["candidate"])
    if value["baseline"]["id"] == value["candidate"]["id"]:
        raise ValueError("baseline and candidate identities must differ")
    fields(value["budget"], "unit max_operations")
    text(value["budget"]["unit"])
    integer(value["budget"]["max_operations"], 1, 10**12)
    integer(value["minimum_correct_weight_gain"], 1, 10**12)
    rows = value["suite"]
    if type(rows) is not list or not 1 <= len(rows) <= 1000:
        raise ValueError("suite must be a nonempty bounded array")
    case_ids = set()
    task_ids = set()
    expected_outcomes = set()
    total_weight = 0
    for row in rows:
        fields(row, "case_id task_sha256 expected weight")
        text(row["case_id"])
        if row["case_id"] in case_ids:
            raise ValueError("duplicate case identity")
        case_ids.add(row["case_id"])
        sha(row["task_sha256"])
        if row["task_sha256"] in task_ids:
            raise ValueError("duplicate frozen task identity")
        task_ids.add(row["task_sha256"])
        _choice(row["expected"], OUTCOMES)
        expected_outcomes.add(row["expected"])
        integer(row["weight"], 1, 10**9)
        total_weight += row["weight"]
    if total_weight > 10**12:
        raise ValueError("suite weight exceeds admitted bound")
    if expected_outcomes != set(OUTCOMES):
        raise ValueError("suite must retain positive and negative controls")
    return value


def _run(raw, plan, plan_sha256, role):
    value = parse(raw)
    fields(value, "schema run_id plan_sha256 role source_id source_sha256 execution_status total_operations cases")
    _choice(value["schema"], (RUN,))
    text(value["run_id"])
    sha(value["plan_sha256"])
    if value["plan_sha256"] != plan_sha256:
        raise ValueError(role + " run plan identity mismatch")
    _choice(value["role"], (role,))
    expected_source = plan[role]
    if (value["source_id"] != expected_source["id"]
            or value["source_sha256"] != expected_source["source_sha256"]):
        raise ValueError(role + " source identity mismatch")
    _choice(value["execution_status"], RUN_STATUSES)
    if value["total_operations"] is not None:
        integer(value["total_operations"], 0, 10**12)
    rows = value["cases"]
    if type(rows) is not list or len(rows) != len(plan["suite"]):
        raise ValueError(role + " run must retain every planned case")
    planned = {row["case_id"]: row for row in plan["suite"]}
    seen = set()
    all_costs_known = True
    summed_cost = 0
    all_completed = True
    has_timeout = False
    for row in rows:
        fields(row, "case_id task_sha256 status observed operations")
        text(row["case_id"])
        if row["case_id"] in seen:
            raise ValueError("duplicate reported case identity")
        seen.add(row["case_id"])
        if row["case_id"] not in planned:
            raise ValueError("unplanned reported case identity")
        if row["task_sha256"] != planned[row["case_id"]]["task_sha256"]:
            raise ValueError("reported task identity mismatch")
        _choice(row["status"], CASE_STATUSES)
        if row["status"] == "COMPLETED":
            _choice(row["observed"], OUTCOMES)
        elif row["observed"] is not None:
            raise ValueError("non-completed case cannot report an outcome")
        else:
            all_completed = False
        has_timeout = has_timeout or row["status"] == "TIMEOUT"
        if row["operations"] is None:
            all_costs_known = False
        else:
            integer(row["operations"], 0, 10**12)
            summed_cost += row["operations"]
            if summed_cost > 10**12:
                raise ValueError("reported operations exceed admitted bound")
    if seen != set(planned):
        raise ValueError(role + " run omitted planned cases")
    if all_costs_known:
        if value["total_operations"] != summed_cost:
            raise ValueError("reported total does not equal retained case operations")
    elif value["total_operations"] is not None:
        raise ValueError("unknown case cost requires unknown total cost")
    status = value["execution_status"]
    if status == "COMPLETE" and (not all_completed or not all_costs_known):
        raise ValueError("complete run must complete every case with known cost")
    if status == "TIMEOUT" and not has_timeout:
        raise ValueError("timeout run must retain a timed-out case")
    if status == "UNKNOWN_COST" and all_costs_known:
        raise ValueError("unknown-cost run must retain an unknown cost")
    if status == "INCOMPLETE" and all_completed and all_costs_known:
        raise ValueError("incomplete run has no retained incompleteness")
    return value


def _metrics(run, plan, baseline_cases=None):
    planned = {row["case_id"]: row for row in plan["suite"]}
    correct_weight = 0
    false_acceptances = []
    regressions = []
    retained = []
    for row in sorted(run["cases"], key=lambda item: item["case_id"]):
        expected = planned[row["case_id"]]
        correct = row["status"] == "COMPLETED" and row["observed"] == expected["expected"]
        false_acceptance = (row["status"] == "COMPLETED"
                            and expected["expected"] == "REJECT"
                            and row["observed"] == "ACCEPT")
        if correct:
            correct_weight += expected["weight"]
        if false_acceptance:
            false_acceptances.append(row["case_id"])
        if (baseline_cases is not None and baseline_cases[row["case_id"]]["correct"]
                and not correct):
            regressions.append(row["case_id"])
        retained.append({"case_id": row["case_id"], "task_sha256": row["task_sha256"],
                         "expected": expected["expected"], "weight": expected["weight"],
                         "status": row["status"], "observed": row["observed"],
                         "operations": row["operations"], "correct": correct,
                         "false_acceptance": false_acceptance})
    return {"run_id": run["run_id"], "execution_status": run["execution_status"],
            "total_operations": run["total_operations"], "correct_weight": correct_weight,
            "false_acceptance_case_ids": false_acceptances,
            "regression_case_ids": regressions, "retained_cases": retained}


def evaluate(plan_raw, baseline_run_raw, candidate_run_raw, expected_plan_sha256):
    """Return canonical evaluation bytes or refuse malformed/unbound evidence."""
    sha(expected_plan_sha256)
    if digest(plan_raw) != expected_plan_sha256:
        raise ValueError("plan digest mismatch")
    plan = _plan(plan_raw)
    baseline = _run(baseline_run_raw, plan, expected_plan_sha256, "baseline")
    candidate = _run(candidate_run_raw, plan, expected_plan_sha256, "candidate")
    baseline_metrics = _metrics(baseline, plan)
    baseline_cases = {row["case_id"]: row for row in baseline_metrics["retained_cases"]}
    candidate_metrics = _metrics(candidate, plan, baseline_cases)
    gain = candidate_metrics["correct_weight"] - baseline_metrics["correct_weight"]
    budget = plan["budget"]["max_operations"]
    reasons = []
    if candidate_metrics["false_acceptance_case_ids"]:
        verdict = "REJECT"
        reasons.append("candidate_false_acceptance")
    elif candidate_metrics["regression_case_ids"]:
        verdict = "REJECT"
        reasons.append("candidate_case_regression")
    elif ((baseline["total_operations"] is not None and baseline["total_operations"] > budget)
          or (candidate["total_operations"] is not None and candidate["total_operations"] > budget)):
        verdict = "REJECT"
        reasons.append("matched_budget_exceeded")
    elif (baseline["execution_status"] != "COMPLETE"
          or candidate["execution_status"] != "COMPLETE"
          or baseline["total_operations"] is None
          or candidate["total_operations"] is None):
        verdict = "INCONCLUSIVE"
        reasons.append("comparison_incomplete_or_cost_unknown")
    elif gain < plan["minimum_correct_weight_gain"]:
        verdict = "REJECT"
        reasons.append("minimum_gain_not_met")
    else:
        verdict = "ACCEPT"
        reasons.append("frozen_acceptance_criterion_met")
    total_weight = sum(row["weight"] for row in plan["suite"])
    result = {
        "schema": EVALUATION,
        "plan_sha256": expected_plan_sha256,
        "baseline_run_sha256": digest(baseline_run_raw),
        "candidate_run_sha256": digest(candidate_run_raw),
        "verdict": verdict,
        "reasons": reasons,
        "scope": "finite_suite_comparison",
        "promotion_authority": "none",
        "cost_measurement": "reported_not_independently_measured",
        "execution_attestation": "none",
        "expected_label_validation": "not_performed",
        "evaluator_source_validation": "local_source_bundle_match",
        "candidate_source_validation": "declared_record_match_only",
        "frozen": {"evaluator": plan["evaluator"], "baseline": plan["baseline"],
                   "candidate": plan["candidate"], "budget": plan["budget"],
                   "minimum_correct_weight_gain": plan["minimum_correct_weight_gain"]},
        "results": {"planned_cases": len(plan["suite"]),
                    "negative_control_cases": sum(row["expected"] == "REJECT" for row in plan["suite"]),
                    "total_weight": total_weight,
                    "correct_weight_gain": gain, "baseline": baseline_metrics,
                    "candidate": candidate_metrics},
    }
    return encode(result)
