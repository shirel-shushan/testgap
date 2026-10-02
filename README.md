# testgap

CLI tool that finds changed-but-untested code in JavaScript repos and (later) generates tests for it with an LLM.

## Install

```sh
pip install -e ".[dev]"
```

## Usage

```sh
testgap run --repo PATH [--base BRANCH] [--all] [--report FILE]
```

- `--base` – branch to diff against (default `main`)
- `--all` – ignore the diff and treat every uncovered line as changed
- `--report` – write a report file (not implemented yet)

Currently supports Vitest (`npx vitest run --coverage`) via `testgap.adapters.vitest`.

## Tests

```sh
pytest
```
