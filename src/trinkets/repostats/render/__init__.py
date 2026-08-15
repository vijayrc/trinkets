"""Output renderers for a :class:`~trinkets.repostats.models.RepoReport`."""

from trinkets.repostats.render.json_out import render_json
from trinkets.repostats.render.markdown import render_markdown

__all__ = ["render_json", "render_markdown"]
