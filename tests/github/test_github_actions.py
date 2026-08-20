"""GitHub actions tests."""
import copy
import json
import subprocess
from pathlib import Path
from typing import cast

import pytest


def run_act(setup_test_repo: dict[str, object], job: str, event: str) -> subprocess.CompletedProcess[str]:
    """Push event."""
    git_path = cast(Path, setup_test_repo["git_path"])
    repo = cast(Path, setup_test_repo["path"])
    subprocess.run(args=[str(git_path), "add", "."], cwd=repo, check=True, shell=False)  # noqa: S603
    subprocess.run(args=[str(git_path), "commit", "--allow-empty", "-m", "init"], cwd=repo, check=True, shell=False)  # noqa
    head = subprocess.run(  # noqa: S603
        args=[git_path, "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    event_data = copy.deepcopy(cast(dict[str, object], setup_test_repo["event_data"]))
    event_data.update({"after": str(head)})
    event_file = cast(Path, setup_test_repo["event_file"])
    event_file.write_text(json.dumps(event_data), encoding="utf-8")
    current_env = cast(dict[str, str], setup_test_repo["env"])
    act_path = cast(Path, setup_test_repo["act_path"])
    act_args = [str(act_path), event, "-j", job, *copy.deepcopy(cast(list[str], setup_test_repo["args"]))]

    try:
        result = subprocess.run(  # noqa: S603
            act_args, capture_output=True, check=True, text=True, env=current_env
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Act failed with exit code {e.returncode}.\nSTDOUT:\n{e.output}\nSTDERR:\n{e.stderr}")
    return result

@pytest.mark.xdist_group(name="serial-git-suite")
@pytest.mark.parametrize(
    ("files", "test", "scan"),
    [
        (["Makefile"], True, True),
        (["trivy.yml"], False, True),
        (["LICENSE"], False, False)
    ]
)
def test_job_changes(setup_test_repo: dict[str, object], files: list[str], test: bool, scan: bool) -> None:
    """Test changes job."""
    repo = cast(Path, setup_test_repo["path"])
    for s in files:
        with open(repo / s, "a", encoding="utf-8") as f:
            f.write("\n")
    result = run_act(setup_test_repo, "changes", "push")

    assert result.returncode == 0, f"The local CI/CD run failed. Logs:\n{result.stdout}"
    assert f"test={str(test).lower()}" in result.stdout.lower()
    assert f"scan={str(scan).lower()}" in result.stdout.lower()

def test_job_lint(setup_test_repo: dict[str, object]) -> None:
    """Test lint job."""
    repo = cast(Path, setup_test_repo["path"])
    with open(repo / "Makefile", "a", encoding="utf-8") as f:
        f.write("\n")
    result = run_act(setup_test_repo, "lint", "push")
    assert result.returncode == 0, f"The local CI/CD run failed. Logs:\n{result.stdout}"

def test_job_test(setup_test_repo: dict[str, object]) -> None:
    """Test job."""
    repo = cast(Path, setup_test_repo["path"])
    with open(repo / "Makefile", "a", encoding="utf-8") as f:
        f.write("\n")
    result = run_act(setup_test_repo, "test", "push")
    assert result.returncode == 0, f"The local CI/CD run failed. Logs:\n{result.stdout}"


def test_job_scan(setup_test_repo: dict[str, object]) -> None:
    """Test scan job."""
    repo = cast(Path, setup_test_repo["path"])
    with open(repo / "Makefile", "a", encoding="utf-8") as f:
        f.write("\n")
    result = run_act(setup_test_repo, "security-scan", "push")
    assert result.returncode == 0, f"The local CI/CD run failed. Logs:\n{result.stdout}"

def test_job_build(setup_test_repo: dict[str, object]) -> None:
    """Test scan job."""
    repo = cast(Path, setup_test_repo["path"])
    with open(repo / "Makefile", "a", encoding="utf-8") as f:
        f.write("\n")
    result = run_act(setup_test_repo, "build-check", "push")
    assert result.returncode == 0, f"The local CI/CD run failed. Logs:\n{result.stdout}"

def test_job_bump(setup_test_repo: dict[str, object]) -> None:
    """Test scan job."""
    repo = cast(Path, setup_test_repo["path"])
    with open(repo / "Makefile", "a", encoding="utf-8") as f:
        f.write("\n")
    result = run_act(setup_test_repo, "bump-version", "workflow_dispatch")
    assert result.returncode == 0, f"The local CI/CD run failed. Logs:\n{result.stdout}"

def test_job_publish_release(setup_test_repo: dict[str, object]) -> None:
    """Test scan job."""
    repo = cast(Path, setup_test_repo["path"])
    with open(repo / "Makefile", "a", encoding="utf-8") as f:
        f.write("\n")
    result = run_act(setup_test_repo, "publish-github-release", "workflow_dispatch")
    assert result.returncode == 0, f"The local CI/CD run failed. Logs:\n{result.stdout}"

def test_job_publish_pypi(setup_test_repo: dict[str, object]) -> None:
    """Test scan job."""
    repo = cast(Path, setup_test_repo["path"])
    with open(repo / "Makefile", "a", encoding="utf-8") as f:
        f.write("\n")
    result = run_act(setup_test_repo, "publish-pypi", "workflow_dispatch")
    assert result.returncode == 0, f"The local CI/CD run failed. Logs:\n{result.stdout}"
