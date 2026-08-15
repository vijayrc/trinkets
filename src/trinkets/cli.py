"""Top-level dispatcher for the trinkets utility collection.

Each utility lives in its own subpackage and exposes a ``register(subparsers)``
function plus a ``run(args)`` entry point.  Adding a new tool means adding one
module here and one line to ``UTILITIES``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from trinkets import __version__

# name -> (module path, one-line help). Imported lazily so a broken or
# heavyweight utility never slows down or breaks the others.
UTILITIES: dict[str, tuple[str, str]] = {
    "repostats": (
        "trinkets.repostats.cli",
        "Analyse a git repository and report languages, build, deps, flow and test stats.",
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trinkets",
        description="A collection of small, self-contained developer utilities.",
    )
    parser.add_argument("--version", action="version", version=f"trinkets {__version__}")

    subparsers = parser.add_subparsers(dest="utility", metavar="<utility>")
    for name, (module_path, help_text) in UTILITIES.items():
        sub = subparsers.add_parser(name, help=help_text, add_help=False)
        sub.set_defaults(_module=module_path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Dispatch on the first token so each utility owns its full argument
    # namespace (including -h) rather than fighting the parent parser.
    if argv and argv[0] in UTILITIES:
        module_path, _ = UTILITIES[argv[0]]
        module = __import__(module_path, fromlist=["main"])
        return int(module.main(argv[1:]))

    parser = build_parser()
    if not argv or argv[0] in {"-h", "--help"}:
        parser.print_help()
        return 0
    parser.parse_args(argv)  # handles --version and reports unknown utilities
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
