"""Text and Markdown rendering of a run and its baseline comparison."""

from __future__ import annotations

from collections import Counter

from .baseline import CHANGED, FIXED, NEW, REGRESSED, REMOVED, UNCHANGED, Change
from .runner import CaseResult

KIND_ORDER = [REGRESSED, FIXED, CHANGED, NEW, REMOVED, UNCHANGED]


def summary_line(results: list[CaseResult]) -> str:
    counts = Counter(r.status for r in results)
    noun = "case" if len(results) == 1 else "cases"
    line = f"{len(results)} {noun}: {counts['pass']} passed, {counts['fail']} failed"
    if counts["error"]:
        line += f", {counts['error']} errored"
    return line


def diff_summary(changes: list[Change]) -> str:
    counts = Counter(c.kind for c in changes)
    return ", ".join(f"{counts[kind]} {kind}" for kind in KIND_ORDER)


def _transition(change: Change) -> str:
    if change.kind == NEW:
        return f"(new) -> {change.after_status}"
    if change.kind == REMOVED:
        return f"{change.before_status} -> (removed)"
    return f"{change.before_status} -> {change.after_status}"


def _sorted(changes: list[Change]) -> list[Change]:
    return sorted(changes, key=lambda c: KIND_ORDER.index(c.kind))


def render_text(
    results: list[CaseResult],
    changes: list[Change] | None = None,
    baseline_label: str = "",
) -> str:
    width = max(len(r.id) for r in results)
    lines = []
    for result in results:
        lines.append(f"{result.status.upper():5}  {result.id:<{width}}  {result.source}".rstrip())
        lines.extend(f"         {failure}" for failure in result.failures())
    lines += ["", summary_line(results)]

    if changes is not None:
        lines += ["", f"Compared with baseline {baseline_label}:"]
        id_width = max(len(c.id) for c in changes)
        for change in _sorted(changes):
            if change.kind == UNCHANGED:
                continue
            lines.append(f"  {change.kind:<9}  {change.id:<{id_width}}  {_transition(change)}")
            lines.extend(f"      {row}" for row in change.diff.splitlines())
        lines.append(f"  {diff_summary(changes)}")
    return "\n".join(lines)


def render_markdown(
    results: list[CaseResult],
    changes: list[Change] | None = None,
    baseline_label: str = "",
) -> str:
    """A report suitable for a pull request comment or a CI job summary."""
    lines = ["## prompt-regress report", "", f"**{summary_line(results)}**", ""]
    lines += ["| Case | Status | Details |", "| --- | --- | --- |"]
    for result in results:
        details = "; ".join(result.failures()).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{result.id}` | {result.status} | {details} |")

    if changes is not None:
        lines += ["", f"### Compared with baseline {baseline_label}", "", diff_summary(changes), ""]
        for change in _sorted(changes):
            if change.kind == UNCHANGED:
                continue
            lines.append(f"- **{change.kind}** `{change.id}`: {_transition(change)}")
            if change.diff:
                lines += ["", "  ```diff"]
                lines += [f"  {row}" for row in change.diff.splitlines()]
                lines += ["  ```", ""]
    return "\n".join(lines).rstrip() + "\n"
