# Development

This guide covers how to develop, test, document, build, and release `reqadence`.

## Setting up the development environment

`reqadence` uses [pixi](https://pixi.sh/latest/) to manage environments and dependencies.

1.  **Clone the repository:**

    ```bash
    git clone git@github.com:durrantlab/reqadence.git
    cd reqadence
    ```

2.  **Install the development environment:**

    ```bash
    pixi install
    ```

3.  **Activate it** (optional; `pixi run` works without it):

    ```bash
    pixi shell
    ```

The workspace defines these environments:

| Environment                        | Purpose                                                                 |
| ---------------------------------- | ----------------------------------------------------------------------- |
| `default`                          | Development: tests, linting, type checking, and packaging on the newest Python. |
| `py312`, `py313`, `py314`, `py315` | Tests on each supported Python version.                                 |
| `lowest`                           | Tests on Python 3.12 with the oldest dependency versions `pyproject.toml` allows. |
| `docs`                             | [Zensical](https://zensical.org/) and mkdocstrings for the docs.        |

`reqadence` is installed into every environment as an editable package, so source changes take effect immediately.
Its runtime dependencies come from `pyproject.toml`, so they are declared in one place.

## Formatting, linting, and type checking

`reqadence` uses [ruff](https://docs.astral.sh/ruff/) for formatting and linting and [ty](https://docs.astral.sh/ty/) for type checking.
Both target Python 3.12, the oldest supported version.

```bash
pixi run format     # sort imports and format the code
pixi run lint       # check lint rules and formatting without changing files
pixi run typecheck  # type-check the package
```

CI runs `lint` and `typecheck` on every pull request.

## Testing

```bash
pixi run tests              # newest Python
pixi run -e py312 tests     # a specific Python version
pixi run -e lowest tests    # oldest allowed dependency versions
pixi run coverage           # report coverage from the last test run
```

CI runs the tests in every test environment on Linux, and on the newest Python on Windows and macOS.
If you raise a minimum version in `pyproject.toml`, run `pixi update` so the `lowest` environment follows it.

## Documentation

The documentation is built with [Zensical](https://zensical.org/) and configured in `zensical.toml`.
To preview changes locally, run:

```bash
pixi run -e docs serve
```

Then open [`http://127.0.0.1:8000/`](http://127.0.0.1:8000/).
The preview rebuilds when you edit the docs, the README, or the package source.

To build the site into `public/` the same way CI does, run:

```bash
pixi run -e docs docs --strict
```

The API reference is generated from docstrings, one page per module, so new modules appear without any extra configuration.
Docstrings use the Google style.
To link to another object, use its full import path, for example `[ClientConfig][reqadence.api.base.ClientConfig]`.

Pushes to `main` deploy the documentation to GitHub Pages.
Pull requests build it in strict mode, so broken links or docstrings fail the check.

## Versioning

The version is derived from git tags by [setuptools-scm](https://setuptools-scm.readthedocs.io/); it is not written in any file.
To release a new version:

1.  Move the `Unreleased` entries in `CHANGELOG.md` under a heading for the new version.
2.  Commit, then create an annotated tag on that commit and push it:

    ```bash
    git tag -a v0.4.0 -m "v0.4.0"
    git push origin v0.4.0
    ```

A build from an untagged or modified checkout gets a development version such as `0.4.1.dev3+g1a2b3c4`.

## Building the package

```bash
pixi run build       # build the sdist and wheel into dist/
pixi run check-dist  # build, then validate the distributions with twine
```

`build` empties `build/` and `dist/` first, so `dist/` only ever holds the current build.

## Publishing to PyPI

Publish from a clean checkout of a release tag, so the distributions carry the release version.
PyPI rejects development versions that carry a local `+g...` suffix.

To try a release on TestPyPI first, run:

```bash
pixi run publish-test
```

When that looks right, publish to PyPI:

```bash
pixi run publish
```

Both tasks rebuild and check the distributions before uploading.
