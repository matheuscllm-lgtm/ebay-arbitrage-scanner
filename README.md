# Price Comparison Tool

A small personal Python utility. It reads a local list of items, looks up a
reference price for each from public sources, fetches current active
fixed-price listings via an official marketplace API, and produces a ranked
table with three plain metrics per row:

- **Discount %** = (reference − listing price) / reference — the filter ("gate")
  that decides whether a row is shown (default 20; override per run);
- **Gross ROI %** = (reference − listing price) / listing price — shown as a column;
- **Spread $** = reference − listing price — raw difference, no fees included.

Reference prices are never invented: graded items use the median of completed
sales of the same item/grade; ungraded items use a public market price with a
labeled fallback. When a source fails, the row is counted in a "funnel"
summary instead of silently disappearing.

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

Copy `watchlist.example.yaml` to `watchlist.yaml` and add your own items (the
file is git-ignored; a fresh clone has no watchlist until you create one).

## Usage

```bash
python main.py --pricing-only                    # reference prices only (no credentials needed)
python main.py --list-groups                     # list watchlist groups (no credentials needed)
python main.py --group <name>                    # scan one watchlist group (default: discount >= 20%)
python main.py --group <name> --min-discount 10 --min-price 5 --include-raw
                                                 # diagnostic run: lower gate, lower floor, ungraded included
python main.py --grades "PSA 10, CGC 10 Pristine"   # restrict this run to specific grades
python main.py --max-pages 2                     # fewer API pages per item (200 listings each)
```

A full run writes a JSON artifact with every evaluated row plus the funnel
counters (default `results/last_scan.json`, kept out of the repo). If the run
has to stop early (authentication failure or repeated API errors) the artifact
is marked `aborted: true` and the process exits with code 1. The report table
is then generated from that artifact by the summary tool:

```bash
python ebay_summary.py results/last_scan.json -o results/report-<date>.md
python ebay_summary.py results/last_scan.json -o results/report-<date>.md --sensitivity 10,15,20
```

It prints the markdown report (all rows, grouped by verdict, each row with the
listing link and the price-reference link, plus the funnel and a reference
coverage line) and saves it to `-o`. With `--sensitivity`, the highest
threshold is the operational one; the lower bands are printed as diagnostics
only, with a per-threshold count table.

Run `python main.py --help` and `python ebay_summary.py --help` for all options.

## Tests

```bash
python -m pytest -q
```

The suite (434 tests) is offline — no network, no credentials; real payloads
and pages are stored under `tests/fixtures/` — and runs in CI on every push and
pull request.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
