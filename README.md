# Price Comparison Tool

A small personal Python utility. It reads a local list of items, looks up a
reference market price for each from a public source, fetches current active
listings via an official marketplace API, and produces a ranked table.

Single-user project. No paid services. Operational details and the comparison
method are kept locally and are not part of this published repository.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # Linux/macOS
```

Some features call an external marketplace API and need credentials provided as
environment variables (`EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`). Without them the
tool still runs in reference-price-only mode. Never commit credentials — see
[SECURITY.md](SECURITY.md).

Copy `watchlist.example.yaml` to `watchlist.yaml` and add your own items.

## Usage

```bash
python main.py --pricing-only   # reference prices only (no credentials needed)
python main.py                  # full run (needs the API credentials above)
```

Run `python main.py --help` for all options.

## Tests

```bash
python -m pytest -q
```

The suite is offline (no network, no credentials) and runs in CI on every push
and pull request.
