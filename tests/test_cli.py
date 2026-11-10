import json

import pytest

from prompt_regress.cli import main

MODEL = '''
def good(prompt):
    return "pong: " + prompt

def reworded(prompt):
    return "pong pong: " + prompt

def bad(prompt):
    return "nope"

def boom(prompt):
    raise RuntimeError("model offline")

def not_text(prompt):
    return {"text": "pong"}

def judge(rubric, output, prompt):
    return 1.0 if "pong" in output else 0.0
'''

CASES = """
cases:
  - id: ping
    prompt: "ping {{n}}"
    vars: {n: 1}
    assert:
      - contains: pong
      - regex: "ping 1$"
  - id: graded
    prompt: "say pong"
    assert:
      - judge: {rubric: "says pong", min_score: 0.5}
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "cli_fake_model.py").write_text(MODEL)
    (tmp_path / "cases.yaml").write_text(CASES)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(*extra):
    return main(["run", "cases.yaml", "--judge", "cli_fake_model:judge", *extra])


def test_all_passing_exits_zero(project, capsys):
    assert run("--model", "cli_fake_model:good") == 0
    out = capsys.readouterr().out
    assert "PASS   ping" in out
    assert "2 cases: 2 passed, 0 failed" in out


def test_failing_case_exits_one_and_explains(project, capsys):
    assert run("--model", "cli_fake_model:bad") == 1
    out = capsys.readouterr().out
    assert "FAIL   ping" in out
    assert "contains: missing 'pong'" in out
    assert "judge score 0.00 is below 0.50" in out


def test_model_exception_is_an_error_not_a_crash(project, capsys):
    assert run("--model", "cli_fake_model:boom") == 1
    out = capsys.readouterr().out
    assert "ERROR  ping" in out
    assert "model raised RuntimeError: model offline" in out
    assert "2 errored" in out


def test_non_string_model_output_is_an_error(project, capsys):
    assert run("--model", "cli_fake_model:not_text") == 1
    assert "model returned dict, expected str" in capsys.readouterr().out


def test_baseline_workflow(project, capsys):
    assert run("--model", "cli_fake_model:good", "--update-baseline") == 0
    saved = json.loads((project / ".prompt-regress/baselines/main.json").read_text())
    assert saved["cases"]["ping"] == {"status": "pass", "output": "pong: ping 1"}
    capsys.readouterr()

    assert run("--model", "cli_fake_model:good", "--baseline", "main") == 0
    assert "0 regressed, 0 fixed, 0 changed, 0 new, 0 removed, 2 unchanged" in capsys.readouterr().out

    # Output changed but still passes: reported, exit 0 unless --fail-on-change.
    assert run("--model", "cli_fake_model:reworded", "--baseline", "main") == 0
    out = capsys.readouterr().out
    assert "changed    ping" in out
    assert "+pong pong: ping 1" in out
    assert run("--model", "cli_fake_model:reworded", "--baseline", "main", "--fail-on-change") == 1
    capsys.readouterr()

    assert run("--model", "cli_fake_model:bad", "--baseline", "main") == 1
    assert "regressed  ping" in capsys.readouterr().out


def test_missing_baseline_is_a_note_not_a_failure(project, capsys):
    assert run("--model", "cli_fake_model:good", "--baseline", "release") == 0
    assert "No baseline at" in capsys.readouterr().out


def test_markdown_report_is_written(project, capsys):
    run("--model", "cli_fake_model:good", "--update-baseline")
    run("--model", "cli_fake_model:bad", "--baseline", "main", "--report", "report.md")
    report = (project / "report.md").read_text()
    assert "| `ping` | fail |" in report
    assert "**regressed** `ping`: pass -> fail" in report
    assert "```diff" in report


def test_model_named_in_the_yaml_file(project, capsys):
    (project / "cases.yaml").write_text("model: cli_fake_model:good\n" + CASES)
    assert main(["run", "cases.yaml", "--judge", "cli_fake_model:judge"]) == 0


@pytest.mark.parametrize(
    "argv, message",
    [
        (["run", "cases.yaml"], "has no model"),
        (["run", "cases.yaml", "--model", "missing_mod_xyz:f"], "cannot import"),
        (["run", "absent.yaml", "--model", "cli_fake_model:good"], "absent.yaml"),
    ],
)
def test_config_problems_exit_two(project, capsys, argv, message):
    assert main(argv) == 2
    assert message in capsys.readouterr().err
