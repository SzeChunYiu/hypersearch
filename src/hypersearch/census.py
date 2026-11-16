"""Frozen exhaustive-census tasks on the same Store, lease, receipt and export path as studies."""
from types import SimpleNamespace

from . import census_contract as contract
from . import study


def run_census(bundle, core, meter=None):
    """Bounded trusted child; the parent interprets and rechecks its output."""
    return study.run_child(bundle, core, "hypersearch.census_worker", contract.verification, meter)


def census_route():
    return SimpleNamespace(
        validate_wrapper=contract.validate_wrapper, execution_identity=contract.execution_identity,
        wrapper=contract.wrapper, validate_receipt=contract.validate_receipt,
        trusted_receipt=contract.trusted_receipt, run=run_census, outcome=contract.outcome,
        receipt_schema="hypersearch.census-receipt/v1", worker="local-bundled-census", required=contract.SCHEMAS,
        exits={"CENSUS_EMPTY": 0, "CENSUS_NONEMPTY": 1}, commands=("run-census", "replay-census"))


def execute(execution, **arguments):
    return study.execute(execution, route=census_route(), **arguments)


def main(args):
    return study.main(args, route=census_route())
