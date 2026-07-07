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
python main.py --list-groups    # list watchlist groups (no credentials needed)
python main.py --group <name>   # scan only the items in one watchlist group
python main.py --include-raw    # also evaluate ungraded (raw) items this run
```

A full run writes a JSON artifact with every evaluated row (default
`results/last_scan.json`, kept out of the repo). The report table is then
generated from that artifact by the summary tool:

```bash
python ebay_summary.py results/last_scan.json -o results/report-<date>.md
```

It prints the markdown report (all rows, grouped by verdict, each row with
the listing link and the price-reference link) and saves it to `-o`.

Run `python main.py --help` for all options.

## Tests

```bash
python -m pytest -q
```

The suite is offline (no network, no credentials) and runs in CI on every push
and pull request.
