<h1 align="center">reqadence</h1>

<h4 align="center">Async foundation for REST API clients with retries, rate limiting, and response caching.</h4>

reqadence is a small, reusable base layer for building asynchronous REST API
clients in Python. Instead of re-implementing the same request-handling logic
for every service, you subclass a single base class and get automatic retries,
rate limiting, response caching, and JSON parsing out of the box.

It is built on top of [httpx](https://www.python-httpx.org/) and is designed to
be the shared foundation for higher-level clients. It also ships with a
ready-to-use client for the [RCSB Protein Data Bank](https://www.rcsb.org/),
which doubles as a reference implementation for building your own.

## Features

- Async-first HTTP client built on `httpx`.
- Automatic retries with exponential backoff and full jitter, honoring
  `Retry-After` headers.
- Leaky-bucket rate limiting via `aiolimiter`.
- Pluggable response caching (RFC 9111 or force-cache) via `hishel`.
- A clear error hierarchy distinguishing transient from permanent failures.
- Fully typed, with JSON and XML response support.
- A built-in RCSB Protein Data Bank client (`RCSBClient`) for fetching entry
  metadata, structure files, and ligand data.

## Installation

Clone the [repository](https://github.com/durrantlab/reqadence):

```bash
git clone https://github.com/durrantlab/reqadence.git
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

reqadence ships with `RCSBClient`, an async client for the
[RCSB Protein Data Bank](https://www.rcsb.org/) with retries, rate limiting, and
caching built in:

```python
import asyncio

from reqadence.api.rcsb import RCSBClient


async def main() -> None:
    async with RCSBClient() as rcsb:
        entry = await rcsb.get_entry("6OAV")
        print(entry.resolution)  # 1.939
        print(entry.r_factors)  # {"r_work": 0.2001, "r_free": 0.236}


asyncio.run(main())
```

`RCSBClient` can also enrich entries with ligand and mutation data through
(`get_enriched_entry`), download structure files (`get_structure`), and resolve
ligand SMILES (`get_ligand_smiles`). See the docstrings for the full API.

To build a client for another service, subclass `BaseAPI` the same way as [`RCSBClient`](reqadence/api/rcsb/client.py).

## Development

We use [pixi](https://pixi.sh/latest/) to manage Python environments and
simplify the developer workflow. If you have already run `pixi install` (see
[Installation](#installation)), the development environment is ready to use.


## License

This project is released under the Apache-2.0 License as specified in
`LICENSE.md`.