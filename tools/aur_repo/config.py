from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


VALID_STATES = {"published", "draft"}


@dataclass(frozen=True)
class PackageConfig:
    name: str
    path: Path
    state: str


@dataclass(frozen=True)
class RepoConfig:
    root: Path
    title: str
    description: str
    repository_url: str
    packages: tuple[PackageConfig, ...]

    def package_names(self) -> list[str]:
        return [package.name for package in self.packages]

    def packages_for_state(self, state: str) -> list[PackageConfig]:
        if state == "all":
            return list(self.packages)
        return [package for package in self.packages if package.state == state]

    def package_map(self) -> dict[str, PackageConfig]:
        return {package.name: package for package in self.packages}


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]


def load_repo_config(root: Path | None = None) -> RepoConfig:
    repo_root = root or repo_root_from_here()
    config_path = repo_root / "metadata" / "repo.toml"
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    repo_raw = raw.get("repo", {})
    package_entries = raw.get("packages", [])
    packages: list[PackageConfig] = []

    for entry in package_entries:
        name = entry["name"]
        path = repo_root / entry["path"]
        state = entry["state"]

        if state not in VALID_STATES:
            raise ValueError(f"unsupported package state for {name}: {state}")
        if path.name != name:
            raise ValueError(f"package path must end with package name: {path}")
        if not path.is_dir():
            raise ValueError(f"package path does not exist: {path}")

        packages.append(PackageConfig(name=name, path=path, state=state))

    return RepoConfig(
        root=repo_root,
        title=repo_raw["title"],
        description=repo_raw["description"],
        repository_url=repo_raw["repository_url"],
        packages=tuple(sorted(packages, key=lambda item: item.name)),
    )
