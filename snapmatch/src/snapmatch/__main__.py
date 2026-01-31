"""Allow running the package with: `python -m snapmatch`.

This delegates to :func:`snapmatch.cli.main`.
"""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
