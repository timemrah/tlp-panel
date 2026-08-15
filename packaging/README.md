# Distribution

Three channels, and what each one needs.

| Channel | Who it reaches | Where it lives |
|---|---|---|
| GitHub release `.deb` | anyone, one download at a time | `gh release` |
| apt repository on GitHub Pages | Debian · Ubuntu, with automatic updates | `.github/workflows/publish.yml` |
| AUR | Arch Linux | `packaging/aur/` |

The AppStream metainfo file (`data/io.github.timemrah.TlpPanel.metainfo.xml`) is
what makes the app appear in GNOME Software and KDE Discover with its name, icon,
screenshot and release notes once any of those channels installs it. Without it a
package installs but stays invisible in the software centre.

<br>

## One-time setup

### 1. A signing key for the apt repository

apt refuses an unsigned repository. Generate a key that belongs to the project,
not to your personal identity:

```sh
gpg --batch --quick-generate-key "TLP Panel Repository <timemrah@gmail.com>" rsa4096 sign never
gpg --list-secret-keys --keyid-format=long   # note the key id
```

Export the private key and keep it somewhere safe — losing it means every user
has to re-add a new key by hand:

```sh
gpg --armor --export-secret-keys <KEYID> > tlp-panel-signing-key.asc
```

### 2. Repository secrets

In **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
|---|---|
| `GPG_PRIVATE_KEY` | the whole contents of `tlp-panel-signing-key.asc` |
| `GPG_PASSPHRASE` | the passphrase, or empty if the key has none |

### 3. Enable Pages

**Settings → Pages → Source: GitHub Actions.** The workflow deploys there; no
`gh-pages` branch is involved.

<br>

## Releasing

Unchanged from before, with one addition — the workflow does the packaging now:

1. Bump the version in `src/tlppanel/__init__.py` **and** `debian/changelog`
2. `make check`
3. `git tag -a vX.Y.Z` · `git push --follow-tags`
4. `gh release create vX.Y.Z --title "TLP Panel X.Y.Z" --notes "..."` — **without** attaching a `.deb`

Publishing the release fires `.github/workflows/publish.yml`, which builds the
`.deb`, attaches it to that release, then rebuilds the apt repository from every
`.deb` in every release and redeploys Pages. Watch it with `gh run watch`.

Add a `<release>` entry to the metainfo file in the same commit as the version
bump — software centres show that text, not the GitHub release notes.

<br>

## AUR

The AUR is a separate git repository, one per package, pushed over SSH.

### First publish

```sh
# an AUR account with your SSH public key added, then:
git clone ssh://aur@aur.archlinux.org/tlp-panel.git aur-tlp-panel
cp packaging/aur/PKGBUILD packaging/aur/.SRCINFO aur-tlp-panel/
cd aur-tlp-panel
git add PKGBUILD .SRCINFO
git commit -m "Initial import: tlp-panel 0.2.3"
git push
```

### Each release

Update `pkgver`, reset `pkgrel=1`, and replace the checksum:

```sh
sha256sum <(curl -sL https://github.com/timemrah/tlp-panel/archive/refs/tags/vX.Y.Z.tar.gz)
```

On an Arch machine `updpkgsums` and `makepkg --printsrcinfo > .SRCINFO` do both
steps. `.SRCINFO` must match `PKGBUILD` or the AUR rejects the push.

Never leave `sha256sums` as `SKIP` — it disables verification for everyone who
installs the package.

<br>

## Not done

- **Flathub.** The app writes `/etc/tlp.d`, runs `tlp` as root and installs a
  polkit action. Under a Flatpak sandbox that needs `--filesystem=host` plus
  host-spawn, which Flathub review rejects for good reason. A system
  configuration tool belongs in a native package.
- **Fedora / openSUSE.** No `.spec` here yet. The Open Build Service would build
  both from one source if that becomes worth doing.
- **Debian proper.** Needs a sponsor and a long review. The apt repository above
  is the shortcut.
