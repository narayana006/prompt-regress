# prompt-regress

> Regression tests for LLM prompts: YAML cases, LLM-judge + deterministic asserts, diff reports in CI.

**Status:** 🚧 Early stage — design and roadmap published, implementation in progress. Stars, issues and ideas welcome.

## Why

Teams change prompts with no tests. A small wording tweak silently breaks behaviour that worked yesterday.

## Planned features

- [ ] Define prompt test cases in YAML (inputs, expected behaviour, asserts)
- [ ] Deterministic asserts: exact match, regex, JSON schema, contains/not-contains
- [ ] LLM-as-judge rubric scoring for fuzzy expectations
- [ ] Baseline snapshots and a diff report of how outputs changed
- [ ] GitHub Action that comments results on every PR
- [ ] Provider-agnostic (any hosted or local model)

## Intended usage

```
prompt-regress run tests/prompts/*.yaml --baseline main
```

_The interface above is the target design and may change._

## Roadmap

1. Core implementation of the first feature set
2. Examples and tests
3. CI and first tagged release
4. Docs and integrations

## Contributing

Contributions are welcome. Open an issue to discuss an idea or pick an unchecked item from the feature list.

## License

[MIT](LICENSE)
