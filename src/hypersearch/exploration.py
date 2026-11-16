"""Admitted exploration tasks: the pinned-program runner, a non-citable record, the same Store and receipts."""
from types import SimpleNamespace

from . import exploration_contract as contract
from . import study
from .program import run_program


def run_exploration(bundle, core, meter=None):
    return run_program(bundle, core, meter, contract=contract)


def exploration_route():
    return SimpleNamespace(
        validate_wrapper=contract.validate_wrapper, execution_identity=contract.execution_identity,
        wrapper=contract.wrapper, validate_receipt=contract.validate_receipt,
        trusted_receipt=contract.trusted_receipt, run=run_exploration, outcome=contract.outcome,
        receipt_schema="hypersearch.exploration-receipt/v1", worker="local-exploration", required=contract.SCHEMAS,
        exits={"EXPLORATION_RECORDED": 0}, commands=("run-exploration", "replay-exploration"))


def execute(execution, **arguments):
    return study.execute(execution, route=exploration_route(), **arguments)


def main(args):
    return study.main(args, route=exploration_route())
