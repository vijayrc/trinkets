"""Command line interface for the repostats utility."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from trinkets import __version__
from trinkets.repostats.analyzer import analyse_repository
from trinkets.repostats.gitio import GitError
from trinkets.repostats.render import render_json, render_markdown, render_terminal

EPILOG = """\
examples:
  repostats                          analyse the current directory
  repostats ~/code/myapp             analyse another repository
  repostats -f json -o report.json   emit machine-readable output
  repostats -f terminal              print a colourised report to the terminal
  repostats --run-coverage           execute the repo's pytest suite to measure coverage

note:
  --run-coverage executes the analysed repository's test suite. Only use it on
  code you trust. Without it, coverage is read from existing reports only.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repostats",
        description="Analyse a git repository: languages, build, purpose, contributors, "
                    "flow, dependencies, size and tests.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path", nargs="?", default=".", help="repository to analyse (default: current directory)"
    )
    parser.add_argument(
        "-f", "--format", choices=("markdown", "json", "terminal"), default="markdown",
        help="output format (default: markdown); 'terminal' renders the same report "
             "with ANSI colour for reading on screen",
    )
    parser.add_argument(
        "-o", "--output", metavar="FILE", help="write to FILE instead of stdout",
    )
    parser.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto",
        help="colour control for --format terminal (default: auto)",
    )
    parser.add_argument(
        "--max-commits", type=int, default=None, metavar="N",
        help="only inspect the most recent N commits (faster on huge histories)",
    )
    parser.add_argument(
        "--max-file-size", type=int, default=2_000_000, metavar="BYTES",
        help="skip files larger than this (default: 2000000)",
    )
    parser.add_argument(
        "--run-coverage", action="store_true",
        help="execute the repository's pytest suite to measure coverage (runs untrusted code)",
    )
    parser.add_argument("--version", action="version", version=f"repostats {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_path = Path(args.path).expanduser()
    if not repo_path.exists():
        print(f"repostats: {repo_path} does not exist", file=sys.stderr)
        return 2

    try:
        report = analyse_repository(
            repo_path,
            max_commits=args.max_commits,
            run_coverage=args.run_coverage,
            max_file_bytes=args.max_file_size,
        )
    except NotADirectoryError as exc:
        print(f"repostats: {exc}", file=sys.stderr)
        return 2
    except GitError as exc:
        print(f"repostats: git error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("repostats: interrupted", file=sys.stderr)
        return 130

    if args.format == "json":
        rendered = render_json(report)
    elif args.format == "terminal":
        use_color = args.color == "always" or (
            args.color == "auto" and not args.output and sys.stdout.isatty()
        )
        rendered = render_terminal(report, color=use_color)
    else:
        rendered = render_markdown(report)

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        print(f"Wrote {args.format} report to {output_path}", file=sys.stderr)
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
