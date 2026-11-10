"""Load test cases from YAML files and resolve ``module:function`` targets."""

from __future__ import annotations

import importlib
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from .asserts import validate_assertion


class ConfigError(Exception):
    """A test file or command-line target is invalid."""


@dataclass
class Case:
    id: str
    prompt: str
    assertions: list[dict]
    source: str = ""
    model: str | None = None
    vars: dict = field(default_factory=dict)


_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def render(template: str, variables: dict, where: str = "") -> str:
    """Replace ``{{name}}`` placeholders. Single braces are left alone, so
    prompts may contain literal JSON."""

    def substitute(match: re.Match) -> str:
        name = match.group(1)
        if name not in variables:
            raise ConfigError(f"{where}: prompt uses '{{{{{name}}}}}' but no such var is defined")
        return str(variables[name])

    return _PLACEHOLDER.sub(substitute, template)


def load_callable(spec: str) -> Callable[..., Any]:
    """Import ``package.module:function`` and return the function.

    The current directory is importable, so a ``my_model.py`` next to the
    tests works without installing anything.
    """
    module_name, sep, attr = spec.partition(":")
    if not sep or not module_name or not attr:
        raise ConfigError(f"'{spec}' is not of the form module:function")
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    try:
        target: Any = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigError(f"cannot import module '{module_name}': {exc}") from exc
    for part in attr.split("."):
        if not hasattr(target, part):
            raise ConfigError(f"module '{module_name}' has no attribute '{attr}'")
        target = getattr(target, part)
    if not callable(target):
        raise ConfigError(f"'{spec}' is not callable")
    return target


def _load_file(path: Path) -> list[Case]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"{path}: {exc.strerror or exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ConfigError(f"{path}: expected a mapping with a 'cases' list")

    file_prompt = data.get("prompt")
    file_vars = data.get("vars") or {}
    file_model = data.get("model")
    cases = []
    for index, raw in enumerate(data["cases"], start=1):
        if not isinstance(raw, dict):
            raise ConfigError(f"{path}: case #{index} must be a mapping")
        case_id = str(raw.get("id") or "").strip()
        where = f"{path}: case '{case_id or '#' + str(index)}'"
        if not case_id:
            raise ConfigError(f"{where}: missing 'id'")
        template = raw.get("prompt", file_prompt)
        if not isinstance(template, str) or not template.strip():
            raise ConfigError(f"{where}: no 'prompt' on the case or the file")
        assertions = raw.get("assert") or []
        if not isinstance(assertions, list) or not assertions:
            raise ConfigError(f"{where}: needs a non-empty 'assert' list")
        for assertion in assertions:
            try:
                validate_assertion(assertion)
            except ValueError as exc:
                raise ConfigError(f"{where}: {exc}") from exc
        variables = {**file_vars, **(raw.get("vars") or {})}
        cases.append(
            Case(
                id=case_id,
                prompt=render(template, variables, where),
                assertions=assertions,
                source=str(path),
                model=raw.get("model", file_model),
                vars=variables,
            )
        )
    return cases


def load_cases(paths: list[str | Path]) -> list[Case]:
    """Load every case from the given files. Case ids must be unique overall
    because the baseline is keyed by id."""
    cases: list[Case] = []
    seen: dict[str, str] = {}
    for path in paths:
        for case in _load_file(Path(path)):
            if case.id in seen:
                raise ConfigError(
                    f"{case.source}: duplicate case id '{case.id}' (also in {seen[case.id]})"
                )
            seen[case.id] = case.source
            cases.append(case)
    if not cases:
        raise ConfigError("no test cases found")
    return cases
