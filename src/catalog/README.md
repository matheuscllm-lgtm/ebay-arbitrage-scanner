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
