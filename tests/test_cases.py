import pytest

from prompt_regress.cases import ConfigError, load_callable, load_cases, render


def write(tmp_path, text, name="cases.yaml"):
    path = tmp_path / name
    path.write_text(text)
    return path


def test_file_level_prompt_and_vars_are_inherited_and_overridable(tmp_path):
    path = write(
        tmp_path,
        """
model: my_model:run
prompt: "{{tone}}: {{ question }}"
vars: {tone: brief}
cases:
  - id: a
    vars: {question: hi}
    assert: [{contains: x}]
  - id: b
    prompt: "custom {{tone}}"
    vars: {tone: long}
    model: other:run
    assert: [{contains: x}]
""",
    )
    a, b = load_cases([path])
    assert a.prompt == "brief: hi"
    assert a.model == "my_model:run"
    assert b.prompt == "custom long"
    assert b.model == "other:run"


def test_single_braces_are_left_alone():
    assert render('Return {"a": 1} for {{x}}', {"x": "y"}) == 'Return {"a": 1} for y'


@pytest.mark.parametrize(
    "text, expected",
    [
        ("- just a list", "'cases' list"),
        ("cases:\n  - assert: [{contains: x}]\n    prompt: p", "missing 'id'"),
        ("cases:\n  - id: a\n    assert: [{contains: x}]", "no 'prompt'"),
        ("cases:\n  - id: a\n    prompt: p", "non-empty 'assert'"),
        ("cases:\n  - id: a\n    prompt: p\n    assert: [{nope: x}]", "unknown assert"),
        ("cases:\n  - id: a\n    prompt: 'p {{who}}'\n    assert: [{contains: x}]", "no such var"),
        ("cases: [", "invalid YAML"),
    ],
)
def test_invalid_files_give_clear_errors(tmp_path, text, expected):
    with pytest.raises(ConfigError, match=expected):
        load_cases([write(tmp_path, text)])


def test_duplicate_ids_across_files_are_rejected(tmp_path):
    body = "cases:\n  - id: same\n    prompt: p\n    assert: [{contains: x}]\n"
    first = write(tmp_path, body, "one.yaml")
    second = write(tmp_path, body, "two.yaml")
    with pytest.raises(ConfigError, match="duplicate case id 'same'"):
        load_cases([first, second])


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_cases([tmp_path / "nope.yaml"])


def test_load_callable_from_current_directory(tmp_path, monkeypatch):
    (tmp_path / "local_model_mod.py").write_text("def run(prompt):\n    return prompt.upper()\n")
    monkeypatch.chdir(tmp_path)
    assert load_callable("local_model_mod:run")("hi") == "HI"


@pytest.mark.parametrize(
    "spec", ["no_colon", "json:", "definitely_not_a_module_xyz:f", "json:nope", "json:__name__"]
)
def test_load_callable_rejects_bad_targets(spec):
    with pytest.raises(ConfigError):
        load_callable(spec)
