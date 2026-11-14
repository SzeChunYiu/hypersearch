"""Bounded strict JSON and raw-artifact identities, not RFC8785/JCS."""
import base64
import hashlib
import json
from pathlib import PurePosixPath
import re

MAX_BUNDLE_BYTES = 1048576
MAX_RECEIPT_BYTES = 2 * MAX_BUNDLE_BYTES


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def parse(data, maximum=MAX_BUNDLE_BYTES):
    if not isinstance(data, bytes) or len(data) > maximum:
        raise ValueError("JSON input exceeds admitted byte bound")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def forbidden(value):
        raise ValueError("non-integer JSON number is unsupported")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=forbidden, parse_float=forbidden)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("malformed JSON encoding or nesting") from error


def fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError("unexpected closed schema fields")


def text(value):
    if type(value) is not str or not value.strip() or len(value) > 256:
        raise ValueError("expected bounded nonempty text")


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("integer outside admitted bounds")


def sha(value, width=64):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{" + str(width) + "}", value):
        raise ValueError("invalid digest identity")


def relative(value):
    text(value)
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in {".", "..", ".git"} for p in path.parts):
        raise ValueError("unsafe artifact path")
    return value


def artifact_bytes(item, maximum=262144):
    fields(item, "path bytes sha256 base64")
    relative(item["path"])
    integer(item["bytes"], 0, maximum)
    sha(item["sha256"])
    if type(item["base64"]) is not str or len(item["base64"]) > 4 * ((maximum + 2) // 3):
        raise ValueError("artifact encoding too large")
    try:
        raw = base64.b64decode(item["base64"], validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("malformed artifact encoding") from error
    if base64.b64encode(raw).decode("ascii") != item["base64"]:
        raise ValueError("noncanonical artifact encoding")
    if len(raw) != item["bytes"] or digest(raw) != item["sha256"]:
        raise ValueError("artifact byte identity mismatch")
    return raw
