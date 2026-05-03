from __future__ import annotations

from pathlib import Path
import subprocess

from aur_repo.config import PackageConfig, RepoConfig


INFRA_PREFIXES = (
    ".github/",
    "metadata/",
    "tools/",
)
INFRA_FILES = {
    "README.md",
}


def _run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=check,
        text=True,
        capture_output=True,
    )


def _object_exists(root: Path, rev: str) -> bool:
    if not rev or set(rev) == {"0"}:
        return False
    result = _run_git(root, "rev-parse", "--verify", "--quiet", rev, check=False)
    return result.returncode == 0


def git_changed_files(root: Path, base: str, head: str) -> list[str]:
    if _object_exists(root, base):
        result = _run_git(root, "diff", "--name-only", base, head)
    else:
        result = _run_git(root, "ls-files")
    return [line for line in result.stdout.splitlines() if line]


def _is_infra_change(path: str) -> bool:
    return path in INFRA_FILES or path.startswith(INFRA_PREFIXES)


def _matches_state(package: PackageConfig, state: str) -> bool:
    return state == "all" or package.state == state


def determine_targets(
    config: RepoConfig,
    mode: str,
    state: str,
    base: str | None = None,
    head: str = "HEAD",
) -> list[PackageConfig]:
    if mode == "all":
        return config.packages_for_state(state)

    if mode != "changed":
        raise ValueError(f"unsupported target mode: {mode}")

    changed_files = git_changed_files(config.root, base or "", head)
    package_map = config.package_map()
    selected: dict[str, PackageConfig] = {}
    infra_changed = False

    for changed in changed_files:
        matched_package = None
        for package in config.packages:
            package_prefix = package.path.relative_to(config.root).as_posix() + "/"
            if changed.startswith(package_prefix):
                matched_package = package
                break

        if matched_package is not None:
            if _matches_state(matched_package, state):
                selected[matched_package.name] = matched_package
            continue

        if _is_infra_change(changed):
            infra_changed = True

    if infra_changed:
        for package in config.packages:
            if _matches_state(package, state):
                selected[package.name] = package

    return sorted(selected.values(), key=lambda item: item.name)
