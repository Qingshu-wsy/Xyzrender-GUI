# Contributing

Bug reports, feature requests, documentation improvements, and code contributions are welcome.

## Before opening an issue

- Check the existing issues to see whether the problem or request has already been reported.
- For bug reports, include the GUI/core version, operating system, steps to reproduce, and a small reproducible input where possible.
- Remove confidential or personal information from input files before sharing them.

## Development setup

Install [uv](https://docs.astral.sh/uv/) and [just](https://github.com/casey/just), then run:

```bash
uv sync --dev
just check
```

`just check` runs formatting, lint, type checks, and the test suite. Add or update tests when changing behavior, and include relevant documentation updates.

## Pull requests

- Keep changes focused and explain the user-visible behavior in the pull request.
- Run `just check` before submitting and report any checks you could not run.
- Do not include generated `build/` or `dist/` output in source-code pull requests.
