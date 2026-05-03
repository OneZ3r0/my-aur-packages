from __future__ import annotations

from pathlib import Path

from aur_repo.config import PackageConfig, RepoConfig


START_MARKER = "<!-- packages:start -->"
END_MARKER = "<!-- packages:end -->"


def parse_srcinfo(path: Path) -> dict[str, list[str]]:
    data: dict[str, list[str]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or "=" not in line:
                continue
            key, value = [part.strip() for part in line.split("=", 1)]
            data.setdefault(key, []).append(value)
    return data


def package_summary(config: RepoConfig, package: PackageConfig) -> dict[str, str]:
    srcinfo_path = package.path / ".SRCINFO"
    if not srcinfo_path.is_file():
        raise FileNotFoundError(f"missing .SRCINFO for published package: {package.name}")

    data = parse_srcinfo(srcinfo_path)
    pkgver = data["pkgver"][0]
    pkgrel = data["pkgrel"][0]
    pkgdesc = data["pkgdesc"][0]
    aur_url = f"https://aur.archlinux.org/packages/{package.name}"

    return {
        "name": package.name,
        "version": f"{pkgver}-{pkgrel}",
        "description": pkgdesc,
        "aur_url": aur_url,
    }


def _default_readme(config: RepoConfig) -> str:
    return "\n".join(
        [
            f"# {config.title}",
            "",
            config.description,
            "",
            f"Source repository: {config.repository_url}",
            "",
            "## GitHub Actions Configuration",
            "",
            "- Secret `AUR_SSH_PRIVATE_KEY`: the private SSH key used to push to AUR.",
            "- Variable `AUR_SSH_KNOWN_HOSTS`: verified `known_hosts` entries for `aur.archlinux.org`.",
            "- Variable `AUR_GIT_USER_NAME`: the git author name used for AUR publish commits.",
            "- Variable `AUR_GIT_USER_EMAIL`: the git author email used for AUR publish commits.",
            "",
            "## Packages",
            START_MARKER,
            END_MARKER,
            "",
        ]
    )


def render_readme(config: RepoConfig, current_text: str | None) -> str:
    package_rows = []
    for package in config.packages_for_state("published"):
        summary = package_summary(config, package)
        package_rows.append(
            "| `{name}` | `{version}` | {description} | [AUR]({aur_url}) |".format(**summary)
        )

    block_lines = [
        START_MARKER,
        "This section is auto-generated from `.SRCINFO` files.",
        "",
        "| Package | Version | Description | AUR |",
        "| --- | --- | --- | --- |",
        *package_rows,
        END_MARKER,
    ]
    block = "\n".join(block_lines)

    text = current_text if current_text is not None else _default_readme(config)
    if START_MARKER not in text or END_MARKER not in text:
        text = _default_readme(config)

    prefix, remainder = text.split(START_MARKER, 1)
    _, suffix = remainder.split(END_MARKER, 1)
    return prefix.rstrip() + "\n\n" + block + suffix


def update_readme(config: RepoConfig) -> bool:
    readme_path = config.root / "README.md"
    current = readme_path.read_text(encoding="utf-8") if readme_path.exists() else None
    rendered = render_readme(config, current)
    if current == rendered:
        return False
    readme_path.write_text(rendered, encoding="utf-8")
    return True
