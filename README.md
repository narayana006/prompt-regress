# prompt-regress

Regression tests for LLM prompts: write cases in YAML, check answers with deterministic asserts, and diff every run against a saved baseline so a wording tweak cannot silently break what worked yesterday.

**Status: early but usable (v0.1.0).** YAML test cases, deterministic asserts, an optional judge hook, baseline snapshots with a diff report, a Markdown report and CI exit codes all work today. A packaged GitHub Action that comments on pull requests is not built yet.

The tool never talks to a model itself. You point it at a Python function of yours that takes a prompt and returns text, so it works with any hosted or local model and needs no API keys of its own.

## Install

Python 3.10 or newer. Install from GitHub (the `prompt-regress` name on PyPI belongs to an unrelated project, so do not `pip install prompt-regress`):

```bash
pip install git+https://github.com/narayana006/prompt-regress
```

Or from a clone, which also gives you the examples:

```bash
git clone https://github.com/narayana006/prompt-regress
cd prompt-regress
pip install -e ".[dev]"
```

## Quick start (offline)

The repository ships a fake model (`examples/fake_model.py`) and a baseline recorded from it, so this runs with no network. From the repository root:

```bash
prompt-regress run examples/support.yaml --model examples.fake_model:reply --baseline main
```

```text
PASS   greeting        examples/support.yaml
PASS   refund-policy   examples/support.yaml
PASS   extract-ticket  examples/support.yaml
PASS   capital         examples/support.yaml

4 cases: 4 passed, 0 failed

Compared with baseline 'main' (.prompt-regress/baselines/main.json):
  0 regressed, 0 fixed, 0 changed, 0 new, 0 removed, 4 unchanged
```

Now pretend someone edited the prompt. `reply_v2` rephrases one answer and stops returning JSON for another:

```bash
prompt-regress run examples/support.yaml --model examples.fake_model:reply_v2 --baseline main
```

```text
PASS   greeting        examples/support.yaml
PASS   refund-policy   examples/support.yaml
FAIL   extract-ticket  examples/support.yaml
         is_json: output is not valid JSON: Expecting value at position 0
         json_schema: output is not valid JSON: Expecting value at position 0
PASS   capital         examples/support.yaml

4 cases: 3 passed, 1 failed

Compared with baseline 'main' (.prompt-regress/baselines/main.json):
  regressed  extract-ticket  pass -> fail
      --- baseline
      +++ current
      @@ -1 +1 @@
      -{"order_id": "A-1042", "intent": "refund", "urgent": false}
      +Sure! The order is A-1042 and the customer wants a refund.
  changed    refund-policy   pass -> pass
      --- baseline
      +++ current
      @@ -1 +1 @@
      -You can request a refund within 30 days of purchase from the Orders page.
      +Refunds are available for 30 days after purchase. Open the Orders page to start one.
  1 regressed, 0 fixed, 1 changed, 0 new, 0 removed, 2 unchanged
```

The command exits with status 1, which fails a CI job.

## Connecting your model

Write one function that takes the rendered prompt and returns the answer as a string. Call whatever you use inside it.

```python
# my_model.py
def llm_call(prompt: str) -> str:
    response = ...  # call your model here
    return response_text
```

Pass it as `module:function`. The current directory is importable, so a file next to your tests is enough:

```bash
prompt-regress run tests/prompts/*.yaml --model my_model:llm_call
```

You can also name the model in the YAML (`model: my_model:llm_call` at the top of a file or on a single case) and leave `--model` off; `--model` on the command line overrides the files.

## Writing test cases

```yaml
model: my_model:llm_call        # optional, see above
prompt: |                       # default prompt for every case in this file
  You are a support agent for an online shop. Answer briefly.
  Customer: {{question}}
vars:                           # optional defaults, merged with each case's vars
  shop: Acme

cases:
  - id: refund-policy           # required, unique across all files in a run
    vars:
      question: "How do I get a refund?"
    assert:
      - contains: ["30 days", "Orders page"]
      - not_contains: "I cannot help"

  - id: extract-ticket
    prompt: "Extract the order id as JSON. Message: {{message}}"   # replaces the file prompt
    vars:
      message: "Order A-1042 arrived broken."
    assert:
      - json_schema:
          type: object
          required: [order_id]
```

`{{name}}` placeholders are filled from `vars`; an undefined name is an error. Single braces are left untouched, so prompts can contain literal JSON.

### Asserts

A case passes when every assert passes.

| Assert | Passes when |
| --- | --- |
| `equals: text` | the output equals the text, ignoring leading and trailing whitespace |
| `contains: text` or a list | every string appears in the output (case-sensitive) |
| `icontains: text` or a list | same, ignoring case |
| `not_contains: text` or a list | none of the strings appear |
| `regex: pattern` | the pattern matches somewhere (`re.search`, multiline) |
| `not_regex: pattern` | the pattern matches nowhere |
| `is_json: true` / `false` | the whole output is / is not valid JSON |
| `json_schema: {...}` | the output is JSON that validates against the schema (draft 2020-12) |
| `max_length: n` | the output has at most `n` characters |
| `judge: {rubric, min_score}` | your judge callable returns a score of at least `min_score` (default 0.7) |

### Judge asserts

For expectations that fixed rules cannot express, supply a second function. It receives `(rubric, output, prompt)` and returns a score between 0 and 1; typically it asks a grading model. It is off unless you pass `--judge`, and a `judge` assert with no judge configured fails rather than passing silently.

```bash
prompt-regress run examples/judged.yaml --judge examples.fake_model:judge
```

```text
PASS   refund-tone  examples/judged.yaml

1 case: 1 passed, 0 failed
```

Judge scores are only as repeatable as your judge. The example judge is a keyword counter, there to show the wiring.

## Baselines

A baseline is a JSON snapshot of each case's status and output. `--baseline main` refers to `.prompt-regress/baselines/main.json`; a value containing `/` or ending in `.json` is used as a path. Commit the file so CI can compare against it.

```bash
# record or accept the current behaviour (uses the name 'main' unless --baseline is given)
prompt-regress run tests/prompts/*.yaml --update-baseline

# compare a later run with it
prompt-regress run tests/prompts/*.yaml --baseline main
```

Each case is reported as one of:

- `regressed`: passed in the baseline, fails now
- `fixed`: failed in the baseline, passes now
- `changed`: same pass/fail status, different output (shown as a unified diff)
- `unchanged`, `new`, `removed`

If the baseline file does not exist yet, the run still happens and a note tells you how to create it.

## Exit codes and CI

| Code | Meaning |
| --- | --- |
| 0 | every case passed |
| 1 | at least one case failed or the model raised; with `--fail-on-change`, also when a passing case's output differs from the baseline |
| 2 | bad input: invalid YAML, unknown assert, model not importable, corrupt baseline |

`--report FILE` writes the same results as Markdown. In GitHub Actions you can send it to the job summary:

```yaml
- run: pip install git+https://github.com/narayana006/prompt-regress
- run: prompt-regress run tests/prompts/*.yaml --baseline main --report "$GITHUB_STEP_SUMMARY"
```

## Feature checklist

- [x] Define prompt test cases in YAML (inputs, expected behaviour, asserts)
- [x] Deterministic asserts: exact match, regex, JSON schema, contains/not-contains
- [x] Judge scoring for fuzzy expectations, through a callable you supply
- [x] Baseline snapshots and a diff report of how outputs changed
- [x] Provider-agnostic: any model reachable from a Python function
- [x] Markdown report and CI exit codes
- [ ] GitHub Action that comments results on every PR
- [ ] Built-in judge prompts and rubric templates
- [ ] Parallel execution, retries and repeated runs per case

## Limitations

- Cases run one at a time, once each. There is no concurrency, retry or timeout handling; put those in your model function if you need them.
- Model outputs that vary between runs will show up as `changed` on every comparison. Use a fixed seed or temperature 0 where your model allows it, and rely on asserts rather than exact snapshots for free-form text.
- Only single-string prompts are supported. For chat-style messages, build them inside your model function from the prompt string.
- No judge is bundled. The `judge` assert only wires in your own grading function.
- The model function is imported and executed as normal Python, so only run test files and model modules you trust.
- Baselines store full model outputs. Do not put secrets or personal data in test prompts if you commit them.

## Contributing

Issues and pull requests are welcome. To work on the code:

```bash
pip install -e ".[dev]"
pytest
```

Please add a test with any behaviour change.

Built and maintained by [Narayana Vemburaj](https://github.com/narayana006).

## License

[MIT](LICENSE)
