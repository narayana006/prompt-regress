# prompt-regress

Regression tests for LLM prompts: YAML cases, LLM-judge + deterministic asserts, diff reports in CI.

> **Project status: planning. There is no working code in this repository yet.**
> This README describes what the project will do. Nothing below can be installed or run today.
> Features are ticked off in the checklist as they are built.

## What it is

A command-line tool and GitHub Action.

**The problem it solves:** Teams change prompts with no tests. A small wording tweak silently breaks behaviour that worked yesterday.

## Who it is for

Teams that keep LLM prompts in a codebase and change them over time.

## How it will work

1. You write test cases in YAML: an input, the prompt to run, and what a good answer must contain or satisfy.
2. The tool runs every case against your model and checks the answers with fixed rules (exact text, regex, JSON schema) and, where rules are too rigid, a grading model.
3. It compares the results with the last accepted run and reports which cases got better, worse or stayed the same, locally or as a pull request comment.

## Planned features

Unticked items are not built yet.

- [ ] Define prompt test cases in YAML (inputs, expected behaviour, asserts)
- [ ] Deterministic asserts: exact match, regex, JSON schema, contains/not-contains
- [ ] LLM-as-judge rubric scoring for fuzzy expectations
- [ ] Baseline snapshots and a diff report of how outputs changed
- [ ] GitHub Action that comments results on every PR
- [ ] Provider-agnostic (any hosted or local model)

## Planned usage

This is the intended interface, shown so you can judge the design. **It does not work yet**, and names may change before the first release.

```bash
prompt-regress run tests/prompts/*.yaml --baseline main
```

## Contributing

Feedback on the design is the most useful contribution right now. Open an issue to suggest a feature, question an approach or describe your use case. Code contributions are welcome once the first version lands.

## Author

Built and maintained by [Narayana Vemburaj](https://github.com/narayana006).

## License

[MIT](LICENSE)
