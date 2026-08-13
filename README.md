<h1 align="center">reqadence</h1>

<h4 align="center">Async foundation for REST API clients with retries, rate limiting, and response caching.</h4>

reqadence is a small, reusable base layer for building asynchronous REST API
clients in Python. Instead of re-implementing the same request-handling logic
for every service, you subclass a single base class and get automatic retries,
rate limiting, response caching, and JSON parsing out of the box.

It is built on top of [httpx](https://www.python-httpx.org/) and is designed to
be the shared foundation for higher-level clients.

## Features

- Async-first HTTP client built on `httpx`.
- Automatic retries with exponential backoff and full jitter, honoring
  `Retry-After` headers.
- Leaky-bucket rate limiting via `aiolimiter`.
- Pluggable response caching (RFC 9111 or force-cache) via `hishel`.
- A clear error hierarchy distinguishing transient from permanent failures.
- Fully typed, with JSON and XML response support.

## Installation

Clone the [repository](https://github.com/durrantlab/reqadence):

```bash
git clone git@github.com:durrantlab/reqadence.git
```

Move into the directory and install with [pixi](https://pixi.sh/latest/):

```bash
cd reqadence
pixi install
```

This creates an isolated environment with all dependencies and installs
`reqadence` into it (as an editable install, per the project's
`pypi-dependencies`). Activate the environment with:

```bash
pixi shell
```

## Usage

> **TODO:**

## Development

We use [pixi](https://pixi.sh/latest/) to manage Python environments and
simplify the developer workflow. If you have already run `pixi install` (see
[Installation](#installation)), the development environment is ready to use.


## License

This project is released under the Apache-2.0 License as specified in
`LICENSE.md`.