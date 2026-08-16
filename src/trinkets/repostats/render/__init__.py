"""Output renderers for a :class:`~trinkets.repostats.models.RepoReport`."""

from trinkets.repostats.render.json_out import render_json
from trinkets.repostats.render.markdown import render_markdown
from trinkets.repostats.render.terminal import render_terminal

__all__ = ["render_json", "render_markdown", "render_terminal"]
