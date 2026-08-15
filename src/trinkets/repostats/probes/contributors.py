"""Probe 4: contributors and commit timeframe."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from trinkets.repostats.gitio import GitError, GitRunner
from trinkets.repostats.models import Contributor, ContributorInfo

RECORD_SEPARATOR = "\x01"
FIELD_SEPARATOR = "\x02"


def _parse_iso_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def analyse(git: GitRunner | None, max_commits: int | None = None) -> ContributorInfo:
    info = ContributorInfo()
    if git is None:
        return info

    try:
        raw = git.log_with_numstat(max_commits=max_commits)
        info.shallow_or_partial = git.is_shallow()
    except GitError:
        return info

    if not raw.strip():
        return info

    # Key on email so the same person under two display names merges; keep the
    # most recently seen name for display.
    by_identity: dict[str, Contributor] = {}
    commits_by_year: dict[str, int] = defaultdict(int)
    commit_dates: list[date] = []
    distinct_days: set[date] = set()
    total_commits = 0

    for record in raw.split(RECORD_SEPARATOR):
        record = record.strip("\n")
        if not record:
            continue

        header, _, body = record.partition("\n")
        parts = header.split(FIELD_SEPARATOR)
        if len(parts) < 5:
            continue
        _sha, author_name, author_email, short_date, iso_date = parts[:5]

        author_email = author_email.strip().lower()
        author_name = author_name.strip()
        identity = author_email or author_name

        contributor = by_identity.get(identity)
        if contributor is None:
            contributor = Contributor(name=author_name, email=author_email)
            by_identity[identity] = contributor
        contributor.name = author_name or contributor.name
        contributor.commits += 1
        total_commits += 1

        commit_day = _parse_iso_date(iso_date) or _parse_iso_date(short_date)
        if commit_day:
            commit_dates.append(commit_day)
            distinct_days.add(commit_day)
            commits_by_year[str(commit_day.year)] += 1
            stamp = commit_day.isoformat()
            if contributor.first_commit is None or stamp < contributor.first_commit:
                contributor.first_commit = stamp
            if contributor.last_commit is None or stamp > contributor.last_commit:
                contributor.last_commit = stamp

        for line in body.splitlines():
            columns = line.split("\t")
            if len(columns) != 3:
                continue
            added, removed, _path = columns
            # "-" marks a binary file; git reports no line counts for those.
            if added.isdigit():
                contributor.insertions += int(added)
            if removed.isdigit():
                contributor.deletions += int(removed)

    if not by_identity:
        return info

    ranked = sorted(by_identity.values(), key=lambda c: (c.commits, c.churn), reverse=True)

    info.total_commits = total_commits
    info.total_authors = len(ranked)
    info.top_contributors = ranked[:15]
    info.commits_by_year = dict(sorted(commits_by_year.items()))
    info.active_days = len(distinct_days)

    if commit_dates:
        info.first_commit = min(commit_dates).isoformat()
        info.last_commit = max(commit_dates).isoformat()

    # Bus factor: how few authors account for >= 50% of commits.
    half = total_commits / 2
    running = 0
    bus_factor = 0
    for contributor in ranked:
        running += contributor.commits
        bus_factor += 1
        if running >= half:
            break
    info.bus_factor = bus_factor
    top_share = (ranked[0].commits / total_commits * 100) if total_commits else 0
    info.bus_factor_note = (
        f"{bus_factor} author(s) account for at least half of all commits; "
        f"the single largest contributor made {top_share:.0f}% of them."
    )

    return info
