"""Command line interface for the repostats utility."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from trinkets import __version__
from trinkets.repostats.analyzer import analyse_repository
from trinkets.repostats.gitio import GitError
from trinkets.repostats.multi import scan
from trinkets.repostats.render import render_json, render_markdown, render_terminal

EPILOG = """\
examples:
  repostats                          analyse the current directory
  repostats ~/code/myapp             analyse another repository
  repostats -f json -o report.json   emit machine-readable output
  repostats -f terminal              print a colourised report to the terminal
  repostats --run-coverage           execute the repo's pytest suite to measure coverage
  repostats scan ~/code -o report/   analyse every repo under a folder into one HTML site

note:
  --run-coverage executes the analysed repository's test suite. Only use it on
  code you trust. Without it, coverage is read from existing reports only.
"""

SCAN_EPILOG = """\
examples:
  repostats scan ~/code                    analyse every repo under ~/code
  repostats scan ~/code -o site/           write the HTML report to site/ instead

Produces an index.html linking to one report.html per repository, and each
report links out to the specific source files it mentions (manifests, largest
files, API endpoint locations, ...).
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


def build_scan_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repostats scan",
        description="Analyse every git repository under a folder and publish one consolidated "
                    "HTML report: an index page linking to a per-repo report, each of which "
                    "links out to the source files it references.",
        epilog=SCAN_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path", nargs="?", default=".",
        help="folder to search for repositories (default: current directory)",
    )
    parser.add_argument(
        "-o", "--output", metavar="DIR", default="repostats-report",
        help="directory to write the HTML report tree to (default: ./repostats-report)",
    )
    parser.add_argument(
        "--max-depth", type=int, default=6, metavar="N",
        help="how many directory levels to search for repositories (default: 6)",
    )
    parser.add_argument(
        "--max-commits", type=int, default=None, metavar="N",
        help="only inspect the most recent N commits per repository",
    )
    parser.add_argument(
        "--max-file-size", type=int, default=2_000_000, metavar="BYTES",
        help="skip files larger than this (default: 2000000)",
    )
    parser.add_argument(
        "--run-coverage", action="store_true",
        help="execute each repository's test suite to measure coverage (runs untrusted code)",
    )
    return parser


def _scan_main(argv: Sequence[str] | None) -> int:
    parser = build_scan_parser()
    args = parser.parse_args(argv)

    root = Path(args.path).expanduser()
    if not root.is_dir():
        print(f"repostats scan: {root} is not a directory", file=sys.stderr)
        return 2

    def log(display_path: str) -> None:
        print(f"analysing {display_path} ...", file=sys.stderr)

    try:
        entries, output_dir = scan(
            root,
            Path(args.output).expanduser(),
            max_depth=args.max_depth,
            max_commits=args.max_commits,
            max_file_bytes=args.max_file_size,
            run_coverage=args.run_coverage,
            on_progress=log,
        )
    except KeyboardInterrupt:
        print("repostats scan: interrupted", file=sys.stderr)
        return 130

    if not entries:
        print(f"repostats scan: no git repositories found under {root}", file=sys.stderr)
        return 1

    ok = sum(1 for e in entries if e.report is not None)
    failed = len(entries) - ok
    print(f"Wrote {ok} report(s) ({failed} failed) to {output_dir / 'index.html'}", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "scan":
        return _scan_main(argv[1:])

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
