"""repostats — analyse a git repository and report on how it is built.

Public entry point::

    from trinkets.repostats import analyse_repository
    report = analyse_repository(Path("~/code/myapp").expanduser())
"""

from trinkets.repostats.analyzer import analyse_repository
from trinkets.repostats.models import RepoReport

__all__ = ["analyse_repository", "RepoReport"]
