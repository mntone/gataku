# AGENTS.md

## Runtime Environment

- Target Python version is 3.13 (official support for 3.11 and newer).
- Use `python -m venv .venv` and `pip install -r requirements.txt` unless told otherwise.

## Code Style

- Indentation with tabs
- Comments must be written in English
- Use type hints and docstrings for new functions; keep existing annotations.
- Follow the JSON formatting rules (tabs, multi-line objects for 2+ keys).
- Commit messages must follow the Conventional Commits style, be written in English,
  and the title (first line) must fit within 55 characters
- Markdown files must be wrapped at 80 characters

## Commits

- Follow Conventional Commits; keep the subject within 55 characters.
- Group related changes (code + schema + docs) into a single commit.
- Avoid mixing unrelated changes; split into separate commits when needed.

## Testing

- Always run `python -m pytest` before and after changes; the suite is fast.
- Add or update tests alongside code changes (especially for config or fetch).
- Do not skip tests unless explicitly requested.

## Logging

- When modifying log formats (download or removed), update tests in
  `tests/test_fetch.py` and related files.
- The removed-media logic (tracker, reasons) must always have unit test coverage.
- Respect existing logging flags (`log_removed`, `log_duplicate`) when adding functionality.

## Configuration Files

- Keep [`config.sample.yaml`](./config.sample.yaml), [`config.schema.json`](./config.schema.json),
  and both READMEs in sync when
  introducing or changing settings.
- Comments inside [`config.sample.yaml`](./config.sample.yaml) must stay concise and in English.
- Update schema/unit tests whenever config parsing changes.

## Documentation

- [`README.md`](./README.md) and [`README.ja.md`](./README.ja.md) must always describe
  the same features; edit both.
- Do not touch the badge area at the top of README.md.
- Mention new configuration options in both READMEs and reference
  [`config.schema.json`](./config.schema.json).
