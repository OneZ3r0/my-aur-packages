#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from aur_repo.config import PackageConfig, RepoConfig, load_repo_config
from aur_repo.publish import publish_package
from aur_repo.readme import update_readme
from aur_repo.targets import determine_targets


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


def _selected_packages(
    config: RepoConfig,
    *,
    package_names: list[str] | None = None,
    packages_json: str | None = None,
    select_all: bool = False,
    state: str = "all",
) -> list[PackageConfig]:
    package_map = config.package_map()

    if packages_json:
        parsed = json.loads(packages_json)
        package_names = list(parsed)
    elif select_all:
        return config.packages_for_state(state)

    if not package_names:
        raise SystemExit("package selection is required")

    selected = []
    for name in package_names:
        package = package_map.get(name)
        if package is None:
            raise SystemExit(f"unknown package: {name}")
        if state != "all" and package.state != state:
            raise SystemExit(f"package {name} is not in state {state}")
        selected.append(package)
    return sorted(selected, key=lambda item: item.name)


def _generate_srcinfo(package: PackageConfig) -> str:
    result = _run(["makepkg", "--printsrcinfo"], cwd=package.path)
    return result.stdout.rstrip() + "\n"


def _check_or_write_srcinfo(package: PackageConfig, write: bool) -> bool:
    generated = _generate_srcinfo(package)
    srcinfo_path = package.path / ".SRCINFO"
    current = srcinfo_path.read_text(encoding="utf-8") if srcinfo_path.exists() else None

    if write:
        if current == generated:
            return False
        srcinfo_path.write_text(generated, encoding="utf-8")
        return True

    if current is None:
        if package.state == "draft":
            return False
        raise SystemExit(f"missing .SRCINFO for published package: {package.name}")

    if current != generated:
        raise SystemExit(f".SRCINFO is out of date for {package.name}")
    return False


def cmd_targets(args: argparse.Namespace) -> int:
    config = load_repo_config()
    if args.package:
        packages = _selected_packages(config, package_names=args.package, state=args.state)
    else:
        packages = determine_targets(
            config,
            mode=args.mode,
            state=args.state,
            base=args.base,
            head=args.head,
        )
    names = [package.name for package in packages]

    if args.format == "json":
        print(json.dumps(names))
    else:
        for name in names:
            print(name)
    return 0


def cmd_srcinfo(args: argparse.Namespace) -> int:
    config = load_repo_config()
    packages = _selected_packages(
        config,
        package_names=args.package,
        packages_json=args.packages_json,
        select_all=args.all,
        state=args.state,
    )

    changed = []
    for package in packages:
        if _check_or_write_srcinfo(package, write=args.write):
            changed.append(package.name)

    if args.format == "json":
        print(json.dumps(changed if args.write else [package.name for package in packages]))
    else:
        for name in (changed if args.write else [package.name for package in packages]):
            print(name)
    return 0


def cmd_readme(_: argparse.Namespace) -> int:
    config = load_repo_config()
    changed = update_readme(config)
    print("changed" if changed else "unchanged")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    config = load_repo_config()
    packages = _selected_packages(
        config,
        package_names=args.package,
        packages_json=args.packages_json,
        select_all=args.all,
        state="published",
    )

    published = []
    for package in packages:
        if publish_package(config, package.name):
            published.append(package.name)

    if args.format == "json":
        print(json.dumps(published))
    else:
        for name in published:
            print(name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repository automation helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    targets = subparsers.add_parser("targets", help="Resolve package targets")
    targets.add_argument("--mode", choices=("changed", "all"), required=True)
    targets.add_argument("--state", choices=("published", "all"), default="all")
    targets.add_argument("--package", action="append", default=[])
    targets.add_argument("--base", default="")
    targets.add_argument("--head", default="HEAD")
    targets.add_argument("--format", choices=("json", "lines"), default="lines")
    targets.set_defaults(func=cmd_targets)

    srcinfo = subparsers.add_parser("srcinfo", help="Check or write .SRCINFO files")
    srcinfo.add_argument("--package", action="append", default=[])
    srcinfo.add_argument("--packages-json")
    srcinfo.add_argument("--all", action="store_true")
    srcinfo.add_argument("--state", choices=("published", "draft", "all"), default="all")
    srcinfo.add_argument("--write", action="store_true")
    srcinfo.add_argument("--format", choices=("json", "lines"), default="lines")
    srcinfo.set_defaults(func=cmd_srcinfo)

    readme = subparsers.add_parser("readme", help="Render README package list")
    readme.set_defaults(func=cmd_readme)

    publish = subparsers.add_parser("publish", help="Publish package(s) to AUR")
    publish.add_argument("--package", action="append", default=[])
    publish.add_argument("--packages-json")
    publish.add_argument("--all", action="store_true")
    publish.add_argument("--format", choices=("json", "lines"), default="lines")
    publish.set_defaults(func=cmd_publish)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
