"""Run cases against a model callable and collect results."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .asserts import AssertResult, Judge, check_output
from .cases import Case

Model = Callable[[str], Any]

PASS, FAIL, ERROR = "pass", "fail", "error"


@dataclass
class CaseResult:
    id: str
    status: str
    output: str = ""
    error: str = ""
    seconds: float = 0.0
    source: str = ""
    asserts: list[AssertResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == PASS

    def failures(self) -> list[str]:
        if self.status == ERROR:
            return [self.error]
        return [f"{a.kind}: {a.message}" for a in self.asserts if not a.passed]


def run_case(case: Case, model: Model, judge: Judge | None = None) -> CaseResult:
    started = time.perf_counter()
    try:
        raw = model(case.prompt)
    except Exception as exc:
        return CaseResult(
            case.id,
            ERROR,
            error=f"model raised {type(exc).__name__}: {exc}",
            seconds=time.perf_counter() - started,
            source=case.source,
        )
    seconds = time.perf_counter() - started
    if not isinstance(raw, str):
        return CaseResult(
            case.id,
            ERROR,
            error=f"model returned {type(raw).__name__}, expected str",
            seconds=seconds,
            source=case.source,
        )
    asserts = check_output(raw, case.assertions, prompt=case.prompt, judge=judge)
    status = PASS if all(a.passed for a in asserts) else FAIL
    return CaseResult(case.id, status, raw, "", seconds, case.source, asserts)


def run_cases(
    cases: list[Case],
    resolve_model: Callable[[Case], Model],
    judge: Judge | None = None,
) -> list[CaseResult]:
    """Run every case. ``resolve_model`` picks the callable for a case, which
    lets individual files or cases point at different models."""
    return [run_case(case, resolve_model(case), judge) for case in cases]
