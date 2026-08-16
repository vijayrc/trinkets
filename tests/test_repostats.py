"""End-to-end and probe-level tests for repostats."""

from __future__ import annotations

import json
from pathlib import Path

from trinkets.repostats import analyse_repository
from trinkets.repostats.multi import discover_repos, scan
from trinkets.repostats.probes.codestats import _blank_comments
from trinkets.repostats.render import render_json, render_markdown

FLASK_APP = '''\
"""A tiny order service."""
from flask import Flask
import psycopg2
import redis

app = Flask(__name__)


@app.route("/orders", methods=["GET"])
def list_orders():
    return []


@app.route("/orders", methods=["POST"])
def create_order():
    return {}, 201
'''

SERVICE_LAYER = '''\
class OrderService:
    def place(self, order):
        return order

    def cancel(self, order_id):
        return None
'''

REPOSITORY_LAYER = '''\
class OrderRepository:
    def save(self, order):
        pass
'''


def _web_repo(make_repo) -> Path:
    return make_repo({
        "README.md": "# Orders API\n\nHandles customer orders end to end.\n",
        "pyproject.toml": (
            '[project]\n'
            'name = "orders-api"\n'
            'description = "Order management HTTP service"\n'
            'dependencies = ["flask>=3", "psycopg2-binary", "redis", "kafka-python"]\n'
        ),
        "src/app.py": FLASK_APP,
        "src/services/order_service.py": SERVICE_LAYER,
        "src/repositories/order_repository.py": REPOSITORY_LAYER,
        "tests/test_orders.py": "def test_list_orders():\n    assert True\n",
        "docker-compose.yml": (
            "services:\n"
            "  db:\n    image: postgres:16\n"
            "  cache:\n    image: redis:7\n"
        ),
    })


# --- 1. languages --------------------------------------------------------

def test_detects_primary_language(make_repo):
    report = analyse_repository(_web_repo(make_repo))
    code_languages = [entry for entry in report.languages if entry.is_code]
    assert code_languages[0].language == "Python"
    assert code_languages[0].files >= 4


def test_config_files_are_not_counted_as_source(make_repo):
    report = analyse_repository(_web_repo(make_repo))
    non_code = {entry.language for entry in report.languages if not entry.is_code}
    assert {"TOML", "YAML", "Markdown"} & non_code


# --- 2. build ------------------------------------------------------------

def test_detects_build_tooling(make_repo):
    report = analyse_repository(_web_repo(make_repo))
    assert "pyproject.toml" in report.build.manifests
    assert report.build.containerised is False
    assert "Docker Compose" in report.build.tools


def test_detects_monorepo_workspaces(make_repo):
    repo = make_repo({
        "package.json": json.dumps({"name": "root", "workspaces": ["packages/a", "packages/b"]}),
        "packages/a/package.json": json.dumps({"name": "a"}),
        "packages/a/index.js": "export const a = 1;\n",
        "packages/b/package.json": json.dumps({"name": "b"}),
        "packages/b/index.js": "export const b = 2;\n",
    })
    report = analyse_repository(repo)
    assert "monorepo" in (report.build.model or "")
    assert "packages/a" in report.build.workspaces


# --- 3. purpose ----------------------------------------------------------

def test_purpose_prefers_declared_description(make_repo):
    report = analyse_repository(_web_repo(make_repo))
    assert "Order management HTTP service" in report.purpose.summary
    assert "HTTP service / web API" in report.purpose.detected_kinds


# --- 4. contributors -----------------------------------------------------

def test_contributor_stats(make_repo):
    report = analyse_repository(_web_repo(make_repo))
    assert report.contributors.total_commits == 1
    assert report.contributors.total_authors == 1
    assert report.contributors.top_contributors[0].name == "Test Dev"
    assert report.contributors.bus_factor == 1
    assert report.contributors.first_commit is not None


def test_non_git_directory_is_handled(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")
    report = analyse_repository(tmp_path)
    assert report.is_git_repo is False
    assert report.contributors.total_commits == 0
    assert any("Not a git repository" in warning for warning in report.warnings)


# --- 5. flow -------------------------------------------------------------

def test_flow_diagram_includes_layers_and_datastores(make_repo):
    report = analyse_repository(_web_repo(make_repo))
    mermaid = report.flow.mermaid
    assert mermaid.startswith("flowchart LR")
    assert "service" in mermaid
    assert "repository" in mermaid
    assert "PostgreSQL" in mermaid


def test_flow_reports_low_signal_honestly(make_repo):
    repo = make_repo({"helpers.py": "def add(a, b):\n    return a + b\n"})
    report = analyse_repository(repo)
    assert "Not enough structural signal" in report.flow.note


# --- 6. dependencies -----------------------------------------------------

def test_dependency_classification(make_repo):
    report = analyse_repository(_web_repo(make_repo))
    categories = report.dependencies.by_category
    assert "PostgreSQL" in categories.get("database", [])
    assert "Redis" in categories.get("cache", [])
    assert "Apache Kafka" in categories.get("messaging", [])
    assert "Flask" in categories.get("web framework", [])


def test_compose_images_become_infrastructure(make_repo):
    report = analyse_repository(_web_repo(make_repo))
    sources = {dep.source for dep in report.dependencies.infrastructure}
    assert "docker-compose.yml" in sources


# --- 7. code stats -------------------------------------------------------

def test_counts_classes_functions_and_endpoints(make_repo):
    report = analyse_repository(_web_repo(make_repo))
    assert report.code.classes == 2
    assert report.code.functions >= 5
    assert report.code.api_endpoints == 2
    routes = {endpoint.route for endpoint in report.code.endpoints}
    assert routes == {"/orders"}


def test_commented_out_routes_are_ignored(make_repo):
    repo = make_repo({
        "pyproject.toml": '[project]\nname = "x"\n',
        "app.py": (
            "from flask import Flask\n"
            "app = Flask(__name__)\n"
            '# @app.route("/ghost")\n'
            '@app.route("/real")\n'
            "def real():\n    return {}\n"
        ),
    })
    report = analyse_repository(repo)
    assert [endpoint.route for endpoint in report.code.endpoints] == ["/real"]


def test_blank_comments_preserves_offsets():
    text = 'a = 1  # @app.get("/x")\nb = 2\n'
    blanked = _blank_comments(text, "Python")
    assert len(blanked) == len(text)
    assert "app.get" not in blanked
    assert blanked.startswith("a = 1")


# --- 8. testing ----------------------------------------------------------

def test_testing_probe_finds_tests(make_repo):
    report = analyse_repository(_web_repo(make_repo))
    assert report.testing.test_files == 1
    assert report.testing.test_functions >= 1
    assert report.testing.coverage_percent is None
    assert "coverage" in report.testing.note.lower()


def test_reads_existing_cobertura_coverage(make_repo):
    repo = make_repo({
        "app.py": "def f():\n    return 1\n",
        "coverage.xml": '<?xml version="1.0"?>\n<coverage line-rate="0.8137"></coverage>\n',
    })
    report = analyse_repository(repo)
    assert report.testing.coverage_percent == 81.37
    assert report.testing.coverage_source is not None


def test_reads_lcov_coverage(make_repo):
    repo = make_repo({
        "app.js": "module.exports = 1;\n",
        "lcov.info": "SF:app.js\nLF:10\nLH:7\nend_of_record\n",
    })
    report = analyse_repository(repo)
    assert report.testing.coverage_percent == 70.0


# --- rendering -----------------------------------------------------------

def test_markdown_report_has_all_eight_sections(make_repo):
    markdown = render_markdown(analyse_repository(_web_repo(make_repo)))
    for heading in (
        "## 1. Programming languages",
        "## 2. Build tooling and project model",
        "## 3. Purpose and overall logic",
        "## 4. Contributors and commit timeframe",
        "## 5. Flow: entry to persistence",
        "## 6. External dependencies and infrastructure",
        "## 7. Size and structure",
        "## 8. Testing and coverage",
    ):
        assert heading in markdown


def test_json_report_round_trips(make_repo):
    payload = json.loads(render_json(analyse_repository(_web_repo(make_repo))))
    assert payload["name"]
    assert payload["code"]["api_endpoints"] == 2
    assert payload["flow"]["mermaid"].startswith("flowchart LR")


def test_untracked_files_are_analysed(make_repo):
    repo = make_repo({"committed.py": "x = 1\n"})
    (repo / "uncommitted.py").write_text("class Later:\n    pass\n", encoding="utf-8")
    report = analyse_repository(repo)
    assert report.code.classes == 1


def test_gitignored_files_are_excluded(make_repo):
    repo = make_repo({
        ".gitignore": "secret.py\n",
        "kept.py": "x = 1\n",
    })
    (repo / "secret.py").write_text("class Secret:\n    pass\n", encoding="utf-8")
    report = analyse_repository(repo)
    assert report.code.classes == 0


# --- multi-repo scan -------------------------------------------------------


def test_discover_repos_finds_siblings_and_skips_non_repos(make_repo, tmp_path):
    make_repo({"a.py": "x = 1\n"}, name="repo-a")
    make_repo({"b.py": "x = 1\n"}, name="repo-b")
    (tmp_path / "not-a-repo").mkdir()
    (tmp_path / "not-a-repo" / "readme.txt").write_text("hi\n", encoding="utf-8")

    found = discover_repos(tmp_path)
    assert {p.name for p in found} == {"repo-a", "repo-b"}


def test_discover_repos_treats_root_itself_as_a_repo(make_repo):
    repo = make_repo({"a.py": "x = 1\n"}, name="solo")
    assert discover_repos(repo) == [repo]


def test_discover_repos_does_not_descend_past_max_depth(make_repo, tmp_path):
    nested_parent = tmp_path / "one" / "two" / "three"
    nested_parent.mkdir(parents=True)
    make_repo({"a.py": "x = 1\n"}, name="one/two/three/deep")

    assert discover_repos(tmp_path, max_depth=1) == []
    assert len(discover_repos(tmp_path, max_depth=6)) == 1


def test_scan_writes_index_and_per_repo_report(make_repo, tmp_path):
    make_repo({
        "pyproject.toml": '[project]\nname = "a"\ndependencies = ["flask"]\n',
        "app.py": "from flask import Flask\napp = Flask(__name__)\n",
    }, name="repo-a")
    make_repo({"b.py": "class B:\n    pass\n"}, name="repo-b")

    output_dir = tmp_path / "report"
    entries, written_to = scan(tmp_path, output_dir)

    assert written_to == output_dir.resolve()
    assert {e.slug for e in entries} == {"repo-a", "repo-b"}
    assert all(e.report is not None and e.error is None for e in entries)

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "repo-a" in index_html and "repo-b" in index_html
    assert (output_dir / "repo-a" / "report.html").exists()
    assert (output_dir / "repo-b" / "report.html").exists()


def test_scan_generates_a_source_page_for_a_referenced_manifest(make_repo, tmp_path):
    make_repo({
        "pyproject.toml": '[project]\nname = "a"\ndependencies = ["flask"]\n',
        "app.py": "from flask import Flask\napp = Flask(__name__)\n",
    }, name="repo-a")

    output_dir = tmp_path / "report"
    entries, _ = scan(tmp_path, output_dir)

    manifest_page = output_dir / "repo-a" / "files" / "pyproject.toml.html"
    assert manifest_page.exists()
    assert "dependencies" in manifest_page.read_text(encoding="utf-8")

    report_html = (output_dir / "repo-a" / "report.html").read_text(encoding="utf-8")
    assert "files/pyproject.toml.html" in report_html


def test_scan_records_errors_without_aborting(make_repo, tmp_path, monkeypatch):
    make_repo({"a.py": "x = 1\n"}, name="repo-a")
    make_repo({"b.py": "x = 1\n"}, name="repo-b")

    import trinkets.repostats.multi as multi_module

    real_analyse = multi_module.analyse_repository

    def flaky_analyse(repo_path, **kwargs):
        if repo_path.name == "repo-b":
            raise multi_module.GitError("simulated failure")
        return real_analyse(repo_path, **kwargs)

    monkeypatch.setattr(multi_module, "analyse_repository", flaky_analyse)

    entries, output_dir = scan(tmp_path, tmp_path / "report")

    by_slug = {e.slug: e for e in entries}
    assert by_slug["repo-a"].report is not None
    assert by_slug["repo-b"].error == "simulated failure"
    assert (output_dir / "repo-a" / "report.html").exists()
    assert not (output_dir / "repo-b").exists()
    assert (output_dir / "index.html").exists()
