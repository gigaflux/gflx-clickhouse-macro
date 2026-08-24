"""conftest for GitHub actions."""
import os
import shutil
import subprocess
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def setup_test_repo() -> Generator[dict[str, object], None, None]:
    """A pytest fixture to initialize an isolated environment with Git repository inside.

    Yields:
        dict[str, object]: Dict with keys path, act, git, env
    """
    git_path = shutil.which("git") # type: ignore[attr-defined]
    act_path = shutil.which("act")  # type: ignore[attr-defined]
    rsync_path = shutil.which("rsync")  # type: ignore[attr-defined]
    uv_path = shutil.which("uv")  # type: ignore[attr-defined]
    npm_path = shutil.which("npm")  # type: ignore[attr-defined]

    if not git_path:
        pytest.fail("The git executable was not found in the current environment PATH.")
    if not act_path:
        pytest.fail("The act executable was not found in the current environment PATH.")
    if not rsync_path:
        pytest.fail("The rsync executable was not found in the current environment PATH.")
    if not uv_path:
        pytest.fail("The uv executable was not found in the current environment PATH.")
    if not npm_path:
        pytest.fail("The npm executable was not found in the current environment PATH.")

    current_env = os.environ.copy()
    user_home = os.path.expanduser("~")
    user_docker_socket = Path(user_home) / ".docker/run/docker.sock"
    system_docker_socket = Path("/var/run/docker.sock")


    if "DOCKER_HOST" not in current_env:
        if user_docker_socket.exists():
            current_env["DOCKER_HOST"] = f"unix://{user_docker_socket.resolve()}"
        elif system_docker_socket.exists():
            current_env["DOCKER_HOST"] = f"unix://{system_docker_socket.resolve()}"
        else:
            pytest.fail("No local Docker socket detected. 'act' might fail to connect.")

    current_env.update({
        "TRIVY_NO_PROGRESS": "true",
        "TRIVY_SKIP_DB_UPDATE": "true",
        "TRIVY_SKIP_JAVA_DB_UPDATE": "true",
        "ACT": "true"
    })

    root_dir = Path(__file__).resolve().parent.parent.parent
    test_repo_base = root_dir / ".var" / uuid.uuid4().hex[:8]
    test_repo_dir = test_repo_base / root_dir.name

    act_artifacts_path= root_dir / ".var" / ".act-artifacts"
    act_cache_path = root_dir / ".var" / ".act-cache"
    Path(act_artifacts_path).mkdir(parents=True, exist_ok=True)
    Path(act_cache_path).mkdir(parents=True, exist_ok=True)

    if test_repo_base.exists():
        shutil.rmtree(test_repo_base, ignore_errors=True)
    test_repo_dir.mkdir(parents=True, exist_ok=True)

    files_result = subprocess.run(  # noqa: S603
        [git_path, "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    manifest_file = Path(f"{test_repo_base}_manifest.txt")
    manifest_file.write_text(files_result.stdout, encoding="utf-8")
    subprocess.run([rsync_path, "-R", f"--files-from={manifest_file}", str(root_dir), str(test_repo_dir)], check=True)  # noqa: S603
    manifest_file.unlink()

    subprocess.run(args=[str(git_path), "init", "-b", "main"], cwd=test_repo_dir, check=True, shell=False) # noqa: S603
    subprocess.run(args=[str(git_path), "config", "user.name", "CI Tester"], cwd=test_repo_dir, check=True, shell=False) # noqa: S603
    subprocess.run( # noqa: S603
        args=[str(git_path), "config", "user.email", "tester@example.com"],
        cwd=test_repo_dir,
        check=True,
        shell=False,
    )
    subprocess.run(args=[str(git_path), "add", "."], cwd=test_repo_dir, check=True, shell=False) # noqa: S603
    subprocess.run(args=[str(git_path), "commit", "-m", "Initial commit"], cwd=test_repo_dir, check=True, shell=False)  # noqa: S603

    init_commit = subprocess.run(  # noqa: S603
        args=[str(git_path), "rev-parse", "HEAD"], cwd=test_repo_dir, capture_output=True, text=True, check=True
    ).stdout.strip()

    event_file = test_repo_dir / ".var" / "event.json"
    event_file.parent.mkdir(parents=True, exist_ok=True)

    yield {
        "path": test_repo_dir.resolve(),
        "git_path": Path(git_path),
        "act_path": Path(act_path),
        "env": current_env,
        "event_file": Path(event_file),
        "event_data": {
            "action": "opened",
            "number": 42,
            "repository_owner": "nektos",
            "repository": {
                "name": str(test_repo_dir.name),
                "owner": {"login": "nektos"},
                "full_name": f"nektos/{test_repo_dir.name}",
                "default_branch": "main",
            },
            "ref": "refs/heads/main",
            "before": str(init_commit),
            "created": False,
            "deleted": False,
            "forced": False,
            "pusher": {"name": "CI Tester", "email": "tester@example.com"},
            "inputs": {"release_tag": "v100.0.0"},
            "pull_request": {
                "number": 42,
                "title": "feat(clickhouse): add custom macro support",
                "user": {"login": "nektos", "id": 123456, "type": "User"},
                "body": "## Description\nTesting local github actions workflow via act tool.",
                "head": {
                    "ref": "feat/macro-support",
                    "sha": "0000000000000000000000000000000000000000",
                    "repo": {"id": 987654, "name": "gflx-clickhouse-macro", "owner": {"login": "nektos", "id": 123456}},
                },
                "base": {
                    "ref": "main",
                    "sha": "0000000000000000000000000000000000000000",
                    "repo": {
                        "id": 987654,
                        "name": "gflx-clickhouse-macro",
                        "owner": {"login": "nektos", "id": 123456},
                    },
                },
            },
            "sender": {"login": "nektos", "id": 123456, "type": "User"},
            "mock_commits": [
                {"commit": {"message": "feat: add clickhouse macro"}, "author": {"login": "nektos"}},
                {"commit": {"message": "fix: escape macro queries", "author": {"name": "nektos"}}, "author": "nektos"},
            ],
        },
        "args": [
            "-e",
            str(str(event_file)),
            "-C",
            str(test_repo_dir),
            "-P",
            "ubuntu-latest=catthehacker/ubuntu:act-latest",
            "--env",
            "TRIVY_NO_PROGRESS=true",
            "--env",
            "TRIVY_SKIP_JAVA_DB_UPDATE=true",
            "--env",
            "ACT=true",
            "--matrix",
            "os:ubuntu-latest",
            "--matrix",
            "python-version:3.12",
            "--pull=false",
            "--rm",
            "--network",
            "bridge",
            "--artifact-server-path",
            str(act_artifacts_path),
            "--cache-server-path",
            str(act_cache_path)
        ],
    }

    if test_repo_base.exists():
        shutil.rmtree(test_repo_base, ignore_errors=True)
