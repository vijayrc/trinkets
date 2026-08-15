"""Report data model.

Every field carries either a measured fact or an explicitly-labelled inference.
Anything derived from naming conventions rather than measurement lives behind a
``confidence`` field so the renderer can mark it as a guess.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Confidence(str, Enum):
    """How much weight a reader should give an inferred field."""

    MEASURED = "measured"      # counted or read directly from a file
    HIGH = "high"              # unambiguous marker file / declared dependency
    MEDIUM = "medium"          # strong convention (e.g. a *Repository.java class)
    LOW = "low"                # weak signal; treat as a hint only


@dataclass
class Evidence:
    """A single observation supporting an inference, so claims stay auditable."""

    detail: str
    path: str | None = None


@dataclass
class LanguageStat:
    language: str
    files: int = 0
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    bytes: int = 0
    is_code: bool = True

    @property
    def share_basis(self) -> int:
        return self.code_lines


@dataclass
class BuildInfo:
    tools: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    backend: str | None = None
    model: str | None = None            # "single project", "monorepo (7 workspaces)", ...
    workspaces: list[str] = field(default_factory=list)
    ci_systems: list[str] = field(default_factory=list)
    containerised: bool = False
    manifests: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class PurposeInfo:
    summary: str = "Could not be determined."
    project_name: str | None = None
    declared_description: str | None = None
    readme_excerpt: str | None = None
    detected_kinds: list[str] = field(default_factory=list)   # web service, CLI, library...
    frameworks: list[str] = field(default_factory=list)
    domain_terms: list[str] = field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Contributor:
    name: str
    email: str
    commits: int = 0
    insertions: int = 0
    deletions: int = 0
    first_commit: str | None = None
    last_commit: str | None = None

    @property
    def churn(self) -> int:
        return self.insertions + self.deletions


@dataclass
class ContributorInfo:
    total_commits: int = 0
    total_authors: int = 0
    first_commit: str | None = None
    last_commit: str | None = None
    active_days: int = 0
    commits_by_year: dict[str, int] = field(default_factory=dict)
    top_contributors: list[Contributor] = field(default_factory=list)
    bus_factor: int = 0
    bus_factor_note: str = ""
    shallow_or_partial: bool = False


@dataclass
class Dependency:
    name: str
    category: str                 # database, cache, messaging, web framework, ...
    source: str                   # which manifest or file declared it
    version: str | None = None
    detail: str | None = None
    confidence: Confidence = Confidence.HIGH


@dataclass
class DependencyInfo:
    declared: list[Dependency] = field(default_factory=list)
    infrastructure: list[Dependency] = field(default_factory=list)  # compose services, images
    by_category: dict[str, list[str]] = field(default_factory=dict)
    total_declared: int = 0


@dataclass
class ApiEndpoint:
    method: str
    route: str
    path: str
    line: int
    framework: str


@dataclass
class CodeStats:
    total_files: int = 0
    analysed_files: int = 0
    skipped_files: int = 0
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    bytes: int = 0
    classes: int = 0
    functions: int = 0
    api_endpoints: int = 0
    endpoints: list[ApiEndpoint] = field(default_factory=list)
    largest_files: list[tuple[str, int]] = field(default_factory=list)
    counts_by_language: dict[str, dict[str, int]] = field(default_factory=dict)
    exact_parse_languages: list[str] = field(default_factory=list)
    heuristic_parse_languages: list[str] = field(default_factory=list)


@dataclass
class TestingInfo:
    frameworks: list[str] = field(default_factory=list)
    runners: list[str] = field(default_factory=list)
    test_files: int = 0
    test_lines: int = 0
    test_functions: int = 0
    source_files: int = 0
    test_to_source_ratio: float = 0.0
    coverage_percent: float | None = None
    coverage_source: str | None = None
    coverage_tools_configured: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    note: str = ""


@dataclass
class FlowNode:
    node_id: str
    label: str
    layer: str
    shape: str = "rect"
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class FlowEdge:
    source: str
    target: str
    label: str | None = None


@dataclass
class FlowInfo:
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)
    mermaid: str = ""
    confidence: Confidence = Confidence.LOW
    note: str = ""


@dataclass
class RepoReport:
    """The complete analysis of one repository."""

    path: str
    name: str
    generated_at: str
    analyser_version: str
    head_commit: str | None = None
    branch: str | None = None
    remote: str | None = None
    is_git_repo: bool = True

    languages: list[LanguageStat] = field(default_factory=list)
    build: BuildInfo = field(default_factory=BuildInfo)
    purpose: PurposeInfo = field(default_factory=PurposeInfo)
    contributors: ContributorInfo = field(default_factory=ContributorInfo)
    flow: FlowInfo = field(default_factory=FlowInfo)
    dependencies: DependencyInfo = field(default_factory=DependencyInfo)
    code: CodeStats = field(default_factory=CodeStats)
    testing: TestingInfo = field(default_factory=TestingInfo)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def encode(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            return value

        return asdict(self, dict_factory=lambda items: {k: encode(v) for k, v in items})
