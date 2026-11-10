import pytest

from prompt_regress.asserts import check_output, validate_assertion


def one(output, assertion, **kwargs):
    (result,) = check_output(output, [assertion], **kwargs)
    return result


def test_equals_ignores_surrounding_whitespace():
    assert one("Paris\n", {"equals": "Paris"}).passed
    assert not one("Paris, France", {"equals": "Paris"}).passed


def test_contains_accepts_a_list_and_reports_what_is_missing():
    assert one("a b c", {"contains": ["a", "c"]}).passed
    result = one("a b c", {"contains": ["a", "z"]})
    assert not result.passed
    assert "missing 'z'" in result.message


def test_contains_is_case_sensitive_but_icontains_is_not():
    assert not one("Hello", {"contains": "hello"}).passed
    assert one("Hello", {"icontains": "hello"}).passed


def test_not_contains():
    assert one("all good", {"not_contains": ["sorry", "cannot"]}).passed
    result = one("sorry, no", {"not_contains": ["sorry", "cannot"]})
    assert not result.passed
    assert "sorry" in result.message


def test_regex_and_not_regex():
    assert one("within 30 days", {"regex": r"\d+ days"}).passed
    assert not one("soon", {"regex": r"\d+ days"}).passed
    assert one("soon", {"not_regex": r"\d+ days"}).passed
    assert not one("within 30 days", {"not_regex": r"\d+ days"}).passed


def test_regex_anchors_work_per_line():
    assert one("first\nsecond", {"regex": "^second$"}).passed


def test_is_json_true_and_false():
    assert one('{"a": 1}', {"is_json": True}).passed
    assert not one("not json", {"is_json": True}).passed
    assert one("not json", {"is_json": False}).passed
    assert not one("[]", {"is_json": False}).passed


def test_json_schema_reports_the_failing_path():
    schema = {
        "type": "object",
        "required": ["intent"],
        "properties": {"intent": {"enum": ["refund", "exchange"]}},
    }
    assert one('{"intent": "refund"}', {"json_schema": schema}).passed
    result = one('{"intent": "chat"}', {"json_schema": schema})
    assert not result.passed
    assert "intent" in result.message
    assert "not valid JSON" in one("oops", {"json_schema": schema}).message


def test_max_length():
    assert one("abc", {"max_length": 3}).passed
    assert not one("abcd", {"max_length": 3}).passed


def test_judge_uses_the_supplied_callable():
    seen = {}

    def judge(rubric, output, prompt):
        seen.update(rubric=rubric, output=output, prompt=prompt)
        return 0.8

    spec = {"judge": {"rubric": "is polite", "min_score": 0.75}}
    assert one("thanks", spec, judge=judge, prompt="p").passed
    assert seen == {"rubric": "is polite", "output": "thanks", "prompt": "p"}
    strict = {"judge": {"rubric": "is polite", "min_score": 0.9}}
    assert not one("thanks", strict, judge=judge).passed


def test_judge_without_a_callable_fails_instead_of_passing_silently():
    result = one("x", {"judge": "is polite"})
    assert not result.passed
    assert "no judge configured" in result.message


def test_judge_that_raises_is_reported_as_a_failure():
    def broken(rubric, output, prompt):
        raise RuntimeError("grader offline")

    result = one("x", {"judge": "is polite"}, judge=broken)
    assert not result.passed
    assert "grader offline" in result.message


@pytest.mark.parametrize(
    "bad",
    [
        "contains",
        {"contains": "a", "regex": "b"},
        {"smells_like": "roses"},
        {"regex": "("},
        {"json_schema": {"type": "nonsense"}},
        {"judge": {"min_score": 0.5}},
    ],
)
def test_malformed_assertions_are_rejected(bad):
    with pytest.raises(ValueError):
        validate_assertion(bad)
