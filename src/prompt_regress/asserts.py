"""Assertions that check a model output.

Each assertion in a YAML case is a single-key mapping, for example
``{"contains": "refund"}``. Every check is deterministic except ``judge``,
which delegates to a callable supplied by the user.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

import jsonschema

# judge(rubric, output, prompt) -> score between 0 and 1 (or a bool)
Judge = Callable[[str, str, str], Any]

DEFAULT_JUDGE_MIN_SCORE = 0.7


@dataclass
class AssertResult:
    kind: str
    passed: bool
    message: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "passed": self.passed, "message": self.message}


def _short(text: Any, limit: int = 60) -> str:
    text = str(text).replace("\n", "\\n")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else [value]


def _parse_json(output: str) -> tuple[Any, str]:
    try:
        return json.loads(output), ""
    except json.JSONDecodeError as exc:
        return None, f"output is not valid JSON: {exc.msg} at position {exc.pos}"


def _equals(output: str, expected: Any, ctx: dict) -> tuple[bool, str]:
    if output.strip() == str(expected).strip():
        return True, ""
    return False, f"expected exactly '{_short(expected)}', got '{_short(output)}'"


def _contains(output: str, expected: Any, ctx: dict) -> tuple[bool, str]:
    missing = [s for s in _as_list(expected) if str(s) not in output]
    return (not missing), "".join(f"missing '{_short(s)}' " for s in missing).strip()


def _icontains(output: str, expected: Any, ctx: dict) -> tuple[bool, str]:
    lowered = output.lower()
    missing = [s for s in _as_list(expected) if str(s).lower() not in lowered]
    return (not missing), "".join(f"missing '{_short(s)}' " for s in missing).strip()


def _not_contains(output: str, expected: Any, ctx: dict) -> tuple[bool, str]:
    found = [s for s in _as_list(expected) if str(s) in output]
    return (not found), "".join(f"found forbidden '{_short(s)}' " for s in found).strip()


def _regex(output: str, expected: Any, ctx: dict) -> tuple[bool, str]:
    if re.search(str(expected), output, re.MULTILINE):
        return True, ""
    return False, f"no match for /{_short(expected)}/"


def _not_regex(output: str, expected: Any, ctx: dict) -> tuple[bool, str]:
    match = re.search(str(expected), output, re.MULTILINE)
    if match is None:
        return True, ""
    return False, f"/{_short(expected)}/ matched '{_short(match.group(0))}'"


def _is_json(output: str, expected: Any, ctx: dict) -> tuple[bool, str]:
    _, error = _parse_json(output)
    valid = not error
    if bool(expected) == valid:
        return True, ""
    return False, error or "output is valid JSON but should not be"


def _json_schema(output: str, expected: Any, ctx: dict) -> tuple[bool, str]:
    data, error = _parse_json(output)
    if error:
        return False, error
    validator = jsonschema.Draft202012Validator(expected)
    problems = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if not problems:
        return True, ""
    first = problems[0]
    where = "/".join(str(p) for p in first.absolute_path) or "(root)"
    return False, f"schema violation at {where}: {first.message}"


def _max_length(output: str, expected: Any, ctx: dict) -> tuple[bool, str]:
    if len(output) <= int(expected):
        return True, ""
    return False, f"output is {len(output)} characters, limit is {expected}"


def _judge(output: str, expected: Any, ctx: dict) -> tuple[bool, str]:
    judge = ctx.get("judge")
    if judge is None:
        return False, "no judge configured (pass --judge module:function)"
    if isinstance(expected, dict):
        rubric = str(expected.get("rubric", ""))
        min_score = float(expected.get("min_score", DEFAULT_JUDGE_MIN_SCORE))
    else:
        rubric, min_score = str(expected), DEFAULT_JUDGE_MIN_SCORE
    score = float(judge(rubric, output, ctx.get("prompt", "")))
    if score >= min_score:
        return True, f"score {score:.2f}"
    return False, f"judge score {score:.2f} is below {min_score:.2f}"


CHECKS: dict[str, Callable[[str, Any, dict], tuple[bool, str]]] = {
    "equals": _equals,
    "contains": _contains,
    "icontains": _icontains,
    "not_contains": _not_contains,
    "regex": _regex,
    "not_regex": _not_regex,
    "is_json": _is_json,
    "json_schema": _json_schema,
    "max_length": _max_length,
    "judge": _judge,
}


def validate_assertion(assertion: Any) -> str:
    """Return the assertion kind, or raise ValueError if it is malformed."""
    if not isinstance(assertion, dict) or len(assertion) != 1:
        raise ValueError(f"each assert must be a single-key mapping, got {assertion!r}")
    kind = next(iter(assertion))
    if kind not in CHECKS:
        raise ValueError(f"unknown assert '{kind}' (known: {', '.join(sorted(CHECKS))})")
    expected = assertion[kind]
    if kind in ("regex", "not_regex"):
        try:
            re.compile(str(expected))
        except re.error as exc:
            raise ValueError(f"invalid regex {expected!r}: {exc}") from exc
    if kind == "json_schema":
        try:
            jsonschema.Draft202012Validator.check_schema(expected)
        except jsonschema.SchemaError as exc:
            raise ValueError(f"invalid JSON schema: {exc.message}") from exc
    if kind == "judge" and isinstance(expected, dict) and "rubric" not in expected:
        raise ValueError("judge assert needs a 'rubric'")
    return kind


def check_output(
    output: str,
    assertions: list[dict],
    *,
    prompt: str = "",
    judge: Judge | None = None,
) -> list[AssertResult]:
    """Run every assertion against ``output`` and return one result each."""
    ctx = {"prompt": prompt, "judge": judge}
    results = []
    for assertion in assertions:
        kind = validate_assertion(assertion)
        try:
            passed, message = CHECKS[kind](output, assertion[kind], ctx)
        except Exception as exc:  # a broken judge must not abort the whole run
            passed, message = False, f"{kind} raised {type(exc).__name__}: {exc}"
        results.append(AssertResult(kind, passed, message))
    return results
