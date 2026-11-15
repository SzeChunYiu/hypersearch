"""Manual native-session handoff; no launcher, credentials or scientific acceptance."""
from . import review_workflow as workflow
from .study_json import parse, encode


def arguments(sub):
    for action in ("register-review", "grant-review", "submit-review", "recover-review"):
        parser = sub.add_parser(action, help=__doc__)
        for name in ("bundle", "consumer-root", "db", "export"):
            parser.add_argument("--" + name, required=True)
        parser.add_argument("--parent-receipt")
        if action == "submit-review":
            parser.add_argument("--grant", required=True)
            parser.add_argument("--report", required=True)


def read(path, maximum):
    with open(path, "rb") as file:
        return file.read(maximum + 1)


def main(args):
    inputs = [args.bundle]
    value = parse(read(args.bundle, 1048576))
    parent = None
    if args.parent_receipt:
        parent = read(args.parent_receipt, 3145728)
        inputs.append(args.parent_receipt)
    extra = []
    if args.command == "submit-review":
        extra = [parse(read(args.grant, 4096), 4096), parse(read(args.report, 1048576))]
        inputs.extend([args.grant, args.report])
    action = getattr(workflow, args.command.removesuffix("-review"))
    result = action(value, *extra, consumer_root=args.consumer_root, database=args.db,
                    export=args.export, inputs=inputs, parent_raw=parent)
    print(encode(result).decode("ascii"))
    return 0
