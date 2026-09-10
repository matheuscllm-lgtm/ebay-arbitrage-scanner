# Generator inputs

These files are public catalog inputs required by `build_watchlist.py`.

Source: matheuscllm-lgtm/scanner-comc at commit `dd952bad4020c72943e0d00c2b5f5e0a46a586f9`.

- `set_catalog.json`: the 123 set names and `year` fields from
  `comc_scanner/comc_set_slugs.json`. COMC listing counts and URL metadata are
  omitted. Blank years retain the existing TCGCSV `publishedOn` fallback.
- `iconic_pokemon.csv`: copied unchanged from
  `comc_scanner/iconic_pokemon.csv`; all 100 ranks agree with the shipped
  1,669-card watchlist.

Regenerate these inputs only as part of an intentional catalog update.

## Identity-only reprints

`celebrations_classic_identity.json` contains all 25 numbered Classic Collection
products returned by https://tcgcsv.com/tcgplayer/3/2931/products on 2026-09-10.
This is the TCGCSV/TCGplayer metadata source already used by the watchlist generator,
not a claim of independent verification by Pokemon. Keep product IDs and source
names; `name` uses `src.pc_sales.clean_card_name`, as in `build_watchlist.py`.
Select numbered products whose Rarity is `Classic Collection`. No price endpoint
is needed, and no market prices belong in this file.

These entries protect matching even when a reprint is not a scan target. They do
not add cards to `watchlist.yaml`, fetch references or increase the API budget.
The catalog is English-only. It is not a complete registry of all Pokemon reprints.
An incomplete catalog means unknown collisions remain possible.
