# my-aur-packages

A small monorepo for maintaining AUR packages with GitHub Actions.

Source repository: https://github.com/OneZ3r0/my-aur-packages

## GitHub Actions Configuration

- Secret `AUR_SSH_PRIVATE_KEY`: the private SSH key used to push to AUR.
- Variable `AUR_SSH_KNOWN_HOSTS`: verified `known_hosts` entries for `aur.archlinux.org`.
- Variable `AUR_GIT_USER_NAME`: the git author name used for AUR publish commits.
- Variable `AUR_GIT_USER_EMAIL`: the git author email used for AUR publish commits.

## Packages

<!-- packages:start -->
This section is auto-generated from `.SRCINFO` files.

| Package | Version | Description | AUR |
| --- | --- | --- | --- |
| `gaomontablet-m5-driver` | `16.0.0.37-1` | Official Gaomon Tablet Linux Driver (M5 V2) | [AUR](https://aur.archlinux.org/packages/gaomontablet-m5-driver) |
| `yakit-bin` | `1.4.7_0429-1` | Cyber Security ALL-IN-ONE Platform (official AppImage release) | [AUR](https://aur.archlinux.org/packages/yakit-bin) |
<!-- packages:end -->
