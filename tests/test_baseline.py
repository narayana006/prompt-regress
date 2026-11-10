import pytest

from prompt_regress.baseline import baseline_path, compare, load_baseline, save_baseline
from prompt_regress.runner import CaseResult


def result(case_id, status="pass", output="out"):
    return CaseResult(case_id, status, output)


def kinds(changes):
    return {c.id: c.kind for c in changes}


def test_baseline_path_from_name_or_path():
    assert str(baseline_path("main")) == ".prompt-regress/baselines/main.json"
    assert str(baseline_path("snapshots/main.json")) == "snapshots/main.json"


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "nested" / "main.json"
    save_baseline(path, [result("a"), result("b", "fail", "bad")])
    assert load_baseline(path) == {
        "a": {"status": "pass", "output": "out"},
        "b": {"status": "fail", "output": "bad"},
    }


def test_missing_baseline_is_none_and_corrupt_baseline_raises(tmp_path):
    assert load_baseline(tmp_path / "none.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ValueError, match="not a valid baseline"):
        load_baseline(bad)
    bad.write_text('{"version": 1}')
    with pytest.raises(ValueError):
        load_baseline(bad)


def test_compare_classifies_every_kind_of_movement():
    baseline = {
        "same": {"status": "pass", "output": "out"},
        "reworded": {"status": "pass", "output": "old words"},
        "broke": {"status": "pass", "output": "good"},
        "healed": {"status": "fail", "output": "bad"},
        "still-bad": {"status": "fail", "output": "bad"},
        "gone": {"status": "pass", "output": "x"},
    }
    changes = compare(
        baseline,
        [
            result("same"),
            result("reworded", output="new words"),
            result("broke", "fail", "worse"),
            result("healed", "pass", "good"),
            result("still-bad", "fail", "bad"),
            result("added"),
        ],
    )
    assert kinds(changes) == {
        "same": "unchanged",
        "reworded": "changed",
        "broke": "regressed",
        "healed": "fixed",
        "still-bad": "unchanged",
        "added": "new",
        "gone": "removed",
    }
    reworded = next(c for c in changes if c.id == "reworded")
    assert "-old words" in reworded.diff and "+new words" in reworded.diff


def test_a_model_error_after_a_pass_is_a_regression():
    changes = compare({"a": {"status": "pass", "output": "ok"}}, [result("a", "error", "")])
    assert kinds(changes) == {"a": "regressed"}
