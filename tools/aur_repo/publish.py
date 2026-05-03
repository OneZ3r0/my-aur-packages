from __future__ import annotations

import json
from pathlib import Path
import os
import shutil
import shlex
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

from aur_repo.config import PackageConfig, RepoConfig
from aur_repo.readme import parse_srcinfo


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for publishing")
    return value


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        print(f"command failed: {shlex.join(args)}", file=sys.stderr)
        if cwd is not None:
            print(f"cwd: {cwd}", file=sys.stderr)
        if result.stdout:
            print("stdout:", file=sys.stderr)
            print(result.stdout, file=sys.stderr, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print("stderr:", file=sys.stderr)
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        result.check_returncode()
    return result


def _prepare_ssh() -> dict[str, str]:
    private_key = _require_env("AUR_SSH_PRIVATE_KEY")
    known_hosts = _require_env("AUR_SSH_KNOWN_HOSTS")

    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    key_path = ssh_dir / "aur"
    known_hosts_path = ssh_dir / "known_hosts"
    key_path.write_text(private_key.rstrip() + "\n", encoding="utf-8")
    known_hosts_path.write_text(known_hosts.rstrip() + "\n", encoding="utf-8")
    key_path.chmod(0o600)
    known_hosts_path.chmod(0o600)

    fingerprint = _run(["ssh-keygen", "-lf", str(key_path)])
    print(f"AUR SSH key fingerprint: {fingerprint.stdout.strip()}", file=sys.stderr)

    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = (
        f"ssh -i {key_path} "
        "-o IdentitiesOnly=yes "
        f"-o UserKnownHostsFile={known_hosts_path} "
        "-o StrictHostKeyChecking=yes"
    )
    return env


def _publish_identity() -> tuple[str, str]:
    return (
        _require_env("AUR_GIT_USER_NAME"),
        _require_env("AUR_GIT_USER_EMAIL"),
    )


def _tracked_package_files(config: RepoConfig, package: PackageConfig) -> list[Path]:
    result = _run(
        ["git", "ls-files", "--", str(package.path.relative_to(config.root))],
        cwd=config.root,
    )
    files = [config.root / line for line in result.stdout.splitlines() if line]
    return sorted(files)


def _reset_worktree(repo_dir: Path) -> None:
    for entry in repo_dir.iterdir():
        if entry.name == ".git":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _sync_package_files(config: RepoConfig, package: PackageConfig, repo_dir: Path) -> None:
    _reset_worktree(repo_dir)
    for source in _tracked_package_files(config, package):
        relative = source.relative_to(package.path)
        target = repo_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _package_version(package: PackageConfig) -> str:
    data = parse_srcinfo(package.path / ".SRCINFO")
    return f"{data['pkgver'][0]}-{data['pkgrel'][0]}"


def _aur_package_exists(package_name: str) -> bool:
    query = urllib.parse.urlencode(
        {
            "v": "5",
            "type": "info",
            "arg[]": package_name,
        }
    )
    with urllib.request.urlopen(f"https://aur.archlinux.org/rpc?{query}", timeout=15) as response:
        data = json.load(response)
    return int(data.get("resultcount", 0)) > 0


def publish_package(config: RepoConfig, package_name: str) -> bool:
    package = config.package_map().get(package_name)
    if package is None:
        raise ValueError(f"unknown package: {package_name}")
    if package.state != "published":
        raise ValueError(f"package is not publishable: {package_name}")
    if not (package.path / ".SRCINFO").is_file():
        raise FileNotFoundError(f"missing .SRCINFO for package: {package_name}")

    env = _prepare_ssh()
    git_user_name, git_user_email = _publish_identity()
    repo_url = f"ssh://aur@aur.archlinux.org/{package.name}.git"

    with tempfile.TemporaryDirectory(prefix=f"aur-{package.name}-") as temp_dir:
        repo_dir = Path(temp_dir) / package.name
        _run(["git", "init", "--initial-branch=master", str(repo_dir)])
        _run(["git", "remote", "add", "origin", repo_url], cwd=repo_dir)

        fetch = _run(
            ["git", "fetch", "--depth=1", "origin", "master"],
            cwd=repo_dir,
            env=env,
            check=False,
        )
        if fetch.returncode == 0:
            _run(["git", "reset", "--hard", "FETCH_HEAD"], cwd=repo_dir)
        elif _aur_package_exists(package.name):
            print(f"failed to fetch existing AUR package: {package.name}", file=sys.stderr)
            if fetch.stdout:
                print("stdout:", file=sys.stderr)
                print(fetch.stdout, file=sys.stderr, end="" if fetch.stdout.endswith("\n") else "\n")
            if fetch.stderr:
                print("stderr:", file=sys.stderr)
                print(fetch.stderr, file=sys.stderr, end="" if fetch.stderr.endswith("\n") else "\n")
            fetch.check_returncode()

        _sync_package_files(config, package, repo_dir)

        _run(["git", "add", "-A"], cwd=repo_dir)
        diff = _run(["git", "diff", "--cached", "--quiet"], cwd=repo_dir, check=False)
        if diff.returncode == 0:
            return False

        _run(["git", "config", "user.name", git_user_name], cwd=repo_dir)
        _run(["git", "config", "user.email", git_user_email], cwd=repo_dir)
        _run(["git", "commit", "-m", f"Update to {_package_version(package)}"], cwd=repo_dir)
        _run(["git", "push", "-u", "origin", "master"], cwd=repo_dir, env=env)
        return True
