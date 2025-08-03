# flatten-pdf

Utility for merging and flattening invoice PDFs. The repository contains a
GitHub Actions workflow for building a signed and notarized macOS application
bundle and DMG.

## Building the macOS Application

The workflow is defined in `.github/workflows/Build-Mac-PDF.yml`. It runs when
you push a Git tag that matches `v*.*.*`. The job installs Python dependencies,
builds the `.app` using PyInstaller, vendors Ghostscript via Homebrew, signs and
notarizes the bundle (when the required secrets are available) and produces an
`InvoiceMerge.dmg`.

### Triggering the workflow

1. Commit all changes to your repository.
2. Tag a version, e.g. `git tag -a v1.0.0 -m "Release 1.0.0"`.
3. Push the tag to GitHub with `git push origin v1.0.0`.
4. GitHub Actions will create the DMG and attach it to the tagged release.

