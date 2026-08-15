"""ANSI-colourised terminal rendering of the markdown report."""

from __future__ import annotations

import re

from trinkets.repostats.models import RepoReport
from trinkets.repostats.render.markdown import render_markdown

RESET = "\033[0m"

COLOR = {
    "h1": "\033[1;95m",
    "h2": "\033[1;96m",
    "h3": "\033[1;93m",
    "bold": "\033[1;97m",
    "italic": "\033[3;37m",
    "code": "\033[38;5;114m",
    "quote": "\033[3;90m",
    "bullet_mark": "\033[92m",
    "border": "\033[90m",
    "header_cell": "\033[1;94m",
    "hr": "\033[90m",
    "fence": "\033[2;37m",
    "tag": "\033[2;90m",
    "bar_label": "\033[96m",
    "bar_fill": "\033[92m",
    "bar_count": "\033[93m",
}

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_HEADER_RE = re.compile(r"^(#{1,3})\s+(.*)$")
_BULLET_RE = re.compile(r"^(\s*)-\s+(.*)$")
_QUOTE_RE = re.compile(r"^>\s?(.*)$")
_BAR_RE = re.compile(r"^(\S+)(\s+)(█+)(\s+\S+)$")


def _wrap(text: str, style: str) -> str:
    """Colour `text` with `style`, re-applying it after any nested resets."""
    return style + text.replace(RESET, RESET + style) + RESET


def _colorize_inline(text: str) -> str:
    text = _INLINE_CODE_RE.sub(lambda m: _wrap(m.group(1), COLOR["code"]), text)
    text = _BOLD_RE.sub(lambda m: _wrap(m.group(1), COLOR["bold"]), text)
    text = _ITALIC_RE.sub(lambda m: _wrap(m.group(1), COLOR["italic"]), text)
    return text


def _split_row(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-+:?", cell) for cell in cells)


def _render_table(rows: list[str]) -> list[str]:
    cell_rows = [_split_row(row) for row in rows]
    header = cell_rows[0]
    body = cell_rows[1:]
    if body and _is_separator_row(body[0]):
        body = body[1:]

    columns = max(len(header), *(len(row) for row in body)) if body else len(header)
    widths = [0] * columns
    for row in [header, *body]:
        for i in range(columns):
            cell = row[i] if i < len(row) else ""
            widths[i] = max(widths[i], len(cell))

    border = COLOR["border"]

    def fmt_row(cells: list[str], header_row: bool) -> str:
        pieces = []
        for i in range(columns):
            raw = cells[i] if i < len(cells) else ""
            style = COLOR["header_cell"] if header_row else ""
            colored = _colorize_inline(raw)
            colored = _wrap(colored, style) if style else colored
            pad = " " * max(0, widths[i] - len(raw))
            pieces.append(colored + pad)
        cell_sep = f" {border}│{RESET} "
        return f"{border}│{RESET} " + cell_sep.join(pieces) + f" {border}│{RESET}"

    def rule(left: str, mid: str, right: str) -> str:
        segments = mid.join("─" * (w + 2) for w in widths)
        return f"{border}{left}{segments}{right}{RESET}"

    lines = [rule("┌", "┬", "┐"), fmt_row(header, header_row=True)]
    lines.append(rule("├", "┼", "┤"))
    for row in body:
        lines.append(fmt_row(row, header_row=False))
    lines.append(rule("└", "┴", "┘"))
    return lines


def _colorize(markdown: str) -> str:
    out: list[str] = []
    lines = markdown.split("\n")
    in_fence = False
    fence_is_mermaid = False
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                fence_is_mermaid = stripped[3:].strip().lower() == "mermaid"
            else:
                in_fence = False
            out.append(_wrap(line, COLOR["fence"]))
            i += 1
            continue

        if in_fence:
            if not fence_is_mermaid:
                bar_match = _BAR_RE.match(line)
                if bar_match:
                    label, gap1, bar, tail = bar_match.groups()
                    out.append(
                        _wrap(label, COLOR["bar_label"])
                        + gap1
                        + _wrap(bar, COLOR["bar_fill"])
                        + _wrap(tail, COLOR["bar_count"])
                    )
                    i += 1
                    continue
            out.append(_wrap(line, COLOR["fence"]))
            i += 1
            continue

        if stripped.startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            out.extend(_render_table(block))
            continue

        if stripped in ("<details>", "</details>") or stripped.startswith("<details>"):
            out.append(_wrap(line, COLOR["tag"]))
            i += 1
            continue

        if stripped == "---":
            out.append(_wrap("─" * 60, COLOR["hr"]))
            i += 1
            continue

        header_match = _HEADER_RE.match(line)
        if header_match:
            hashes, text = header_match.groups()
            level = len(hashes)
            style = COLOR.get(f"h{level}", COLOR["h3"])
            out.append(_wrap(f"{hashes} {_colorize_inline(text)}", style))
            i += 1
            continue

        quote_match = _QUOTE_RE.match(line)
        if quote_match:
            body = _colorize_inline(quote_match.group(1))
            out.append(_wrap(f"┃ {body}", COLOR["quote"]))
            i += 1
            continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            indent, body = bullet_match.groups()
            mark = _wrap("•", COLOR["bullet_mark"])
            out.append(f"{indent}{mark} {_colorize_inline(body)}")
            i += 1
            continue

        out.append(_colorize_inline(line))
        i += 1

    return "\n".join(out)


def render_terminal(report: RepoReport, *, color: bool = True) -> str:
    """Render the report as the markdown report, styled with ANSI colour.

    Set `color=False` to strip the ANSI codes back out (e.g. when the
    destination isn't a real terminal).
    """
    ansi = _colorize(render_markdown(report))
    if color:
        return ansi
    return _ANSI_RE.sub("", ansi)
