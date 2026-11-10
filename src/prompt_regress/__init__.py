"""Regression tests for LLM prompts."""

from .asserts import AssertResult, check_output
from .baseline import compare, load_baseline, save_baseline
from .cases import Case, ConfigError, load_cases, load_callable
from .runner import CaseResult, run_cases

__version__ = "0.1.0"

__all__ = [
    "AssertResult",
    "Case",
    "CaseResult",
    "ConfigError",
    "check_output",
    "compare",
    "load_baseline",
    "load_callable",
    "load_cases",
    "run_cases",
    "save_baseline",
]
