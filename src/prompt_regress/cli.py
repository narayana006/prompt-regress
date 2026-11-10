"""Command-line interface: ``prompt-regress run FILES... --model module:function``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .baseline import (
    BASELINE_DIR,
    CHANGED,
    REGRESSED,
    baseline_path,
    compare,
    load_baseline,
    save_baseline,
)
from .cases import Case, ConfigError, load_callable, load_cases
from .report import render_markdown, render_text
from .runner import run_cases

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prompt-regress", description="Regression tests for LLM prompts."
    )
    parser.add_argument("--version", action="version", version=f"prompt-regress {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run YAML test cases against a model callable")
    run.add_argument("files", nargs="+", help="YAML test files")
    run.add_argument(
        "--model",
        metavar="MODULE:FUNCTION",
        help="callable taking the prompt (str) and returning the answer (str); "
        "overrides any 'model:' set in the YAML files",
    )
    run.add_argument(
        "--judge",
        metavar="MODULE:FUNCTION",
        help="callable (rubric, output, prompt) -> score in [0, 1], used by 'judge' asserts",
    )
    run.add_argument(
        "--baseline",
        metavar="NAME",
        help=f"compare with a saved snapshot: a name stored under {BASELINE_DIR}/ or a .json path",
    )
    run.add_argument(
        "--update-baseline",
        action="store_true",
        help="save this run as the baseline (named by --baseline, default 'main')",
    )
    run.add_argument(
        "--fail-on-change",
        action="store_true",
        help="also exit 1 when a passing case's output differs from the baseline",
    )
    run.add_argument("--report", metavar="FILE", help="also write a Markdown report to FILE")
    return parser


def _model_resolver(override: str | None):
    cache: dict[str, object] = {}

    def resolve(case: Case):
        spec = override or case.model
        if not spec:
            raise ConfigError(
                f"{case.source}: case '{case.id}' has no model; "
                "pass --model module:function or set 'model:' in the file"
            )
        if spec not in cache:
            cache[spec] = load_callable(spec)
        return cache[spec]

    return resolve


def cmd_run(args: argparse.Namespace) -> int:
    cases = load_cases(args.files)
    resolve = _model_resolver(args.model)
    for case in cases:  # fail fast on a bad target before calling any model
        resolve(case)
    judge = load_callable(args.judge) if args.judge else None

    results = run_cases(cases, resolve, judge)

    changes = None
    label = ""
    notes = []
    name = args.baseline or ("main" if args.update_baseline else None)
    if name:
        path = baseline_path(name)
        label = f"'{name}' ({path})"
        if args.update_baseline:
            save_baseline(path, results)
            notes.append(f"Baseline {label} updated with {len(results)} cases.")
        else:
            try:
                baseline = load_baseline(path)
            except ValueError as exc:
                raise ConfigError(str(exc)) from exc
            if baseline is None:
                notes.append(
                    f"No baseline at {path}; run again with --update-baseline to create it."
                )
            else:
                changes = compare(baseline, results)

    print(render_text(results, changes, label))
    for note in notes:
        print(f"\n{note}")
    if args.report:
        Path(args.report).write_text(render_markdown(results, changes, label), encoding="utf-8")

    if any(not r.passed for r in results):
        return EXIT_FAILED
    if args.fail_on_change and changes and any(c.kind in (CHANGED, REGRESSED) for c in changes):
        return EXIT_FAILED
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return cmd_run(args)
    except ConfigError as exc:
        print(f"prompt-regress: error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
