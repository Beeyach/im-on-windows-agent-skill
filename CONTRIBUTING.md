# Contributing

Contributions should prevent a concrete Windows coding-agent failure without changing unrelated machine settings.

1. Open an issue with the shell, path style, command, and smallest safe reproduction.
2. Add or update a focused test before changing detection logic.
3. Keep the helper dependency-free and compatible with Python 3.10 or newer.
4. Run `python -m unittest discover -s tests -v`.
5. Explain false-positive risk in the pull request.

Avoid rules based only on an agent brand. The active shell and execution environment are what matter.
