"""Baseline snapshots and the comparison between a run and a snapshot."""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path

from .runner import CaseResult

BASELINE_DIR = ".prompt-regress/baselines"
FORMAT_VERSION = 1

# How a case moved relative to the baseline.
REGRESSED = "regressed"  # passed before, fails now
FIXED = "fixed"  # failed before, passes now
CHANGED = "changed"  # same pass/fail status, different output
UNCHANGED = "unchanged"
NEW = "new"  # not in the baseline
REMOVED = "removed"  # in the baseline, not in this run


def baseline_path(name: str, directory: str | Path = BASELINE_DIR) -> Path:
    """A bare name such as ``main`` maps to ``<dir>/main.json``; anything that
    looks like a path is used as given."""
    if name.endswith(".json") or "/" in name or "\\" in name:
        return Path(name)
    return Path(directory) / f"{name}.json"


def save_baseline(path: Path, results: list[CaseResult]) -> None:
    payload = {
        "version": FORMAT_VERSION,
        "cases": {r.id: {"status": r.status, "output": r.output} for r in results},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_baseline(path: Path) -> dict[str, dict] | None:
    """Return ``{case_id: {"status", "output"}}`` or None if there is no file."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases = payload["cases"]
        if not isinstance(cases, dict):
            raise TypeError("'cases' is not a mapping")
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"{path}: not a valid baseline file ({exc})") from exc
    return cases


@dataclass
class Change:
    id: str
    kind: str
    before_status: str | None = None
    after_status: str | None = None
    diff: str = ""


def _output_diff(before: str, after: str) -> str:
    lines = difflib.unified_diff(
        before.splitlines(), after.splitlines(), "baseline", "current", lineterm="", n=1
    )
    return "\n".join(lines)


def compare(baseline: dict[str, dict], results: list[CaseResult]) -> list[Change]:
    """Classify every case in the run and every case dropped from it."""
    changes = []
    for result in results:
        previous = baseline.get(result.id)
        if previous is None:
            changes.append(Change(result.id, NEW, None, result.status))
            continue
        before_ok = previous.get("status") == "pass"
        before_output = previous.get("output", "")
        diff = _output_diff(before_output, result.output) if before_output != result.output else ""
        if before_ok and not result.passed:
            kind = REGRESSED
        elif not before_ok and result.passed:
            kind = FIXED
        elif diff:
            kind = CHANGED
        else:
            kind = UNCHANGED
        changes.append(Change(result.id, kind, previous.get("status"), result.status, diff))
    current_ids = {r.id for r in results}
    for case_id in sorted(set(baseline) - current_ids):
        changes.append(Change(case_id, REMOVED, baseline[case_id].get("status"), None))
    return changes
