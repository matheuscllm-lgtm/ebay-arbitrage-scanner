"""Gera a watchlist do eBay no padrao COMC (operador, 2026-09-03) -- reproduzivel.

Universo = catalogo de 123 sets (``src/catalog/set_catalog.json``, os mesmos 12
grupos da COMC em ``src/groups.py``) x 100 "chases" (``src/catalog/iconic_pokemon.csv``)
x raridade >= Holo Rare (tcgcsv ``Rarity``), teto ``--cap`` cartas por set (as mais
caras pelo market TCGplayer). A pagina do PriceCharting (``pc_url``, referencia de
vendas) e resolvida por nome+numero+set com o MESMO matcher exato do scan
(``pc_sales.product_page_url``); carta sem pagina NAO entra (sem referencia possivel)
e e listada no relatorio -- nunca se inventa URL.

Uso:
    python build_watchlist.py                     # todos os grupos -> watchlist.yaml
    python build_watchlist.py --groups 3-4 --cap 30 --out watchlist.yaml
    python build_watchlist.py --no-pc             # so catalogo (pc_url vazio; scan nao roda)

A saida e versionada no repo (decisao do operador 2026-09-03): um clone limpo
ja tem a watchlist; `main.py --group N` filtra pelo numero do grupo.
"""
import argparse
import csv
import io
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from src import groups, pc_sales
from src import tcg_reference as tcg

CATALOG_DIR = Path(__file__).resolve().parent / "src" / "catalog"
ICONIC_CSV = CATALOG_DIR / "iconic_pokemon.csv"
DEFAULT_CAP = 30
PC_MAX_CONSECUTIVE_ERRORS = 5

# Raridades (tcgcsv `Rarity`, minusculo) que entram: holo/ultra/secret e afins.
# "Rare" (nao-holo), Common/Uncommon, Code Card e vazio ficam fora.
RARITY_ALLOW = frozenset({
    "holo rare", "rare holo", "ultra rare", "rare ultra", "secret rare", "rare secret",
    "illustration rare", "special illustration rare", "hyper rare", "rainbow rare",
    "rare rainbow", "double rare", "shiny holo rare", "shiny rare", "shiny ultra rare",
    "rare shiny", "rare shiny gx", "amazing rare", "radiant rare", "ace spec rare",
    "rare ace", "prism rare", "rare prism star", "rare break", "rare holo ex",
    "rare holo gx", "rare holo v", "rare holo vmax", "rare holo vstar", "rare holo lv.x",
    "rare prime", "rare legend", "legend", "rare holo star", "classic collection",
    "trainer gallery rare holo", "rare holo secret", "rare holo rainbow", "promo",
})


def load_iconic(path=ICONIC_CSV):
    """{nome minusculo: rank} dos 100 chases (coluna `pokemon`, `rank`)."""
    with open(path, encoding="utf-8") as f:
        return {r["pokemon"].strip().lower(): int(r["rank"]) for r in csv.DictReader(f)}


def iconic_regex(rank_of):
    """Palavra inteira, nome mais longo primeiro ("Mewtwo" antes de "Mew")."""
    names = sorted(rank_of, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b", re.I)


def match_pokemon(product_name, rx, rank_of):
    """(Pokemon, rank) do nome do produto, ou None se nao e um chase."""
    m = rx.search(product_name or "")
    if not m:
        return None
    key = m.group(1).lower()
    return m.group(1).title() if key.islower() else m.group(1), rank_of[key]


def numerator(number):
    """'004/102' -> '4'; '199/165' -> '199'; 'TG04/TG30' -> 'TG04'; '' -> ''."""
    head = str(number or "").split("/")[0].strip()
    if head.isdigit():
        return head.lstrip("0") or "0"
    return head


def query_set_name(set_name):
    """Nome do set para a busca no eBay: sem codigo ("SV10: ", "SWSH07: ") e sem
    parenteses -- "SV10: Destined Rivals" -> "Destined Rivals"."""
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", pc_sales.clean_set_name(set_name))).strip()


def _ext(product, key):
    for e in product.get("extendedData") or []:
        if e.get("name") == key:
            return str(e.get("value") or "").strip()
    return ""


def market_by_product(prices):
    out = {}
    for row in prices or []:
        m = row.get("marketPrice")
        if isinstance(m, (int, float)) and m > 0:
            out[row.get("productId")] = max(out.get(row.get("productId"), 0.0), float(m))
    return out


def select_candidates(set_name, products, prices, rank_of, rx, cap=DEFAULT_CAP,
                      rarity_allow=RARITY_ALLOW):
    """Cartas do set que sao chase + raridade aceita + numero, ordenadas por market
    (desc), cortadas no teto. Cada item: name (limpo), number (numerador),
    number_raw, rarity, market, pokemon, pokemon_rank, tcg_url, product_id."""
    market = market_by_product(prices)
    rows = []
    for p in products or []:
        raw_name = str(p.get("name") or "")
        number_raw = _ext(p, "Number")
        rarity = _ext(p, "Rarity")
        if not number_raw or rarity.lower() not in rarity_allow:
            continue
        hit = match_pokemon(raw_name, rx, rank_of)
        if not hit:
            continue
        pokemon, rank = hit
        rows.append({
            "name": pc_sales.clean_card_name(raw_name), "name_raw": raw_name,
            "number": numerator(number_raw), "number_raw": number_raw,
            "rarity": rarity, "market": market.get(p.get("productId")),
            "pokemon": pokemon, "pokemon_rank": rank,
            "tcg_url": str(p.get("url") or ""), "product_id": p.get("productId"),
            "set": set_name,
        })
    rows.sort(key=lambda r: (-(r["market"] or 0.0), r["pokemon_rank"], r["number"]))
    # tcgcsv repete a MESMA carta em productIds diferentes (Mew ex 205 Hyper/Double
    # Rare, Charizard Base Set 4, Celebi Triumphant 3): mesmo nome+numero = mesma
    # pagina no PriceCharting = 2 chamadas ao eBay e 2 linhas iguais na entrega.
    # Como a lista ja vem por market decrescente, o primeiro e o mais caro.
    seen: set[tuple[str, str]] = set()
    uniq = []
    for r in rows:
        key = (r["name"].strip().lower(), r["number"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq[:cap] if cap else uniq


def to_entry(cand, group_number, year, pc_url):
    """Item da watchlist (chaves do WatchCard + campos do catalogo)."""
    return {
        "name": cand["name"],
        "set": cand["set"],
        "number": cand["number"],
        "language": "EN",
        "pc_url": pc_url,
        "tcg_set": cand["set"],
        "ebay_query": f"pokemon {cand['name']} {cand['number']} {query_set_name(cand['set'])}",
        "group": str(group_number),
        "pokemon": cand["pokemon"],
        "pokemon_rank": cand["pokemon_rank"],
        "rarity": cand["rarity"],
        "year": int(year) if str(year or "").isdigit() else None,
    }


def render_yaml(entries, note=""):
    head = (
        "# watchlist.yaml -- GERADA por build_watchlist.py (padrao COMC, 2026-09-03). Nao editar a mao:\n"
        "# regenere com `python build_watchlist.py`. Universo = 123 sets x 100 chases x raridade\n"
        "# >= Holo Rare, teto por set; pc_url = pagina exata da carta no PriceCharting.\n"
    )
    if note:
        head += "# " + note.replace("\n", "\n# ") + "\n"
    body = yaml.safe_dump({"cards": entries}, allow_unicode=True, sort_keys=False, width=200)
    return head + body


def build(group_numbers, fetch_json=None, resolve_pc=None, cap=DEFAULT_CAP,
          log=print, skip_pc=False, pc_cache_dir=None):
    """Monta as entradas dos grupos pedidos. Devolve (entries, report)."""
    fetch_json = fetch_json or tcg._fetch_json
    resolve_pc = resolve_pc or pc_sales.product_page_url
    rank_of = load_iconic()
    rx = iconic_regex(rank_of)
    catalog = groups.catalog()
    tcg_groups = tcg._results(fetch_json(f"{tcg.TCGCSV_BASE}/groups"))
    by_name = {str(g.get("name") or "").strip().lower(): g for g in tcg_groups}
    report = {"per_group": Counter(), "candidates": 0, "no_pc": [], "pc_error": [],
              "missing_tcg_group": [], "capped_sets": [], "pc_collision": []}
    entries = []
    pc_errors_in_a_row = 0
    for n in group_numbers:
        gdef = groups.SCAN_GROUPS[n]
        for set_name in gdef.sets:
            g = by_name.get(set_name.strip().lower())
            if not g or g.get("groupId") is None:
                report["missing_tcg_group"].append(set_name)
                log(f"  [grupo {n}] {set_name}: SEM grupo no tcgcsv -- pulado")
                continue
            gid = g["groupId"]
            products = tcg._results(fetch_json(f"{tcg.TCGCSV_BASE}/{gid}/products"))
            prices = tcg._results(fetch_json(f"{tcg.TCGCSV_BASE}/{gid}/prices"))
            all_rows = select_candidates(set_name, products, prices, rank_of, rx, cap=0)
            rows = all_rows[:cap] if cap else all_rows
            if cap and len(all_rows) > cap:
                report["capped_sets"].append((set_name, len(all_rows)))
            report["candidates"] += len(rows)
            year = (catalog.get(set_name) or {}).get("year")
            if not str(year or "").strip():
                # catalogo sem ano (os 13 sets SV): usar o publishedOn do tcgcsv --
                # fonte real, nada inventado.
                year = str(g.get("publishedOn") or "")[:4]
            kept = 0
            for cand in rows:
                pc_url = ""
                if not skip_pc:
                    if pc_errors_in_a_row >= PC_MAX_CONSECUTIVE_ERRORS:
                        report["pc_error"].append((set_name, cand["name"], cand["number"], "breaker"))
                        continue
                    try:
                        pc_url = resolve_pc(cand["name_raw"], cand["number_raw"], set_name,
                                            cache_dir=pc_cache_dir) or ""
                        pc_errors_in_a_row = 0
                    except pc_sales.PcError as exc:
                        pc_errors_in_a_row += 1
                        report["pc_error"].append((set_name, cand["name"], cand["number"], str(exc)[:80]))
                        continue
                    if not pc_url:
                        report["no_pc"].append((set_name, cand["name"], cand["number"]))
                        continue
                entries.append(to_entry(cand, n, year, pc_url))
                kept += 1
            report["per_group"][n] += kept
            log(f"  [grupo {n}] {set_name}: {len(rows)} candidatas -> {kept} na watchlist")
    # Guarda dura: duas cartas DIFERENTES na mesma pagina do PriceCharting seria uma
    # referencia de preco de OUTRA carta. O dedupe de `select_candidates` ja tira a
    # carta repetida do tcgcsv; o que sobrar aqui e erro de casamento e tem de aparecer.
    by_url: dict[str, list[tuple[str, str, str]]] = {}
    for e in entries:
        if e["pc_url"]:
            by_url.setdefault(e["pc_url"], []).append((e["set"], e["name"], e["number"]))
    colliding: set[str] = set()
    for url, cards in by_url.items():
        if len(cards) > 1:
            report["pc_collision"].append((url, cards))
            colliding.add(url)
            log(f"  COLISAO: {len(cards)} cartas na mesma pagina {url}")
    # Reportar nao basta: enquanto as duas ficarem na watchlist, o scan usa o preco de uma
    # como referencia da OUTRA. Como nao da para saber qual das duas e a dona da pagina,
    # as duas saem do artefato -- o operador ve a colisao no relatorio e no codigo de saida.
    if colliding:
        entries = [e for e in entries if e["pc_url"] not in colliding]
    return entries, report


def report_text(report, entries):
    lines = [f"Watchlist: {len(entries)} cartas"]
    lines.append("Por grupo: " + ", ".join(f"{n}={c}" for n, c in sorted(report["per_group"].items())))
    lines.append(f"Candidatas (apos teto): {report['candidates']} · sem pagina no PriceCharting: "
                 f"{len(report['no_pc'])} · erro PriceCharting: {len(report['pc_error'])} · "
                 f"sets sem grupo tcgcsv: {len(report['missing_tcg_group'])} · "
                 f"sets no teto: {len(report['capped_sets'])}")
    for s in report["missing_tcg_group"]:
        lines.append(f"  SEM tcgcsv: {s}")
    for s, n in report["capped_sets"]:
        lines.append(f"  teto: {s} ({n} candidatas)")
    for s, name, num in report["no_pc"]:
        lines.append(f"  sem PC: {s} | {name} {num}")
    for s, name, num, err in report["pc_error"]:
        lines.append(f"  ERRO PC: {s} | {name} {num} | {err}")
    for url, cards in report.get("pc_collision", []):
        nomes = "; ".join(f"{st} | {name} {num}" for st, name, num in cards)
        lines.append(f"  COLISAO (mesma pagina para cartas diferentes): {url} -> {nomes}")
    return "\n".join(lines)


def main(argv=None):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--groups", default="all", help="grupos: all | 3 | 5-8 | 1,3,10-12")
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP, help="teto de cartas por set (0 = sem teto)")
    ap.add_argument("--out", default="watchlist.yaml")
    ap.add_argument("--no-pc", action="store_true", help="nao resolver pc_url (so catalogo)")
    ap.add_argument("--pc-cache-dir", default=None)
    args = ap.parse_args(argv)
    try:
        nums = groups.parse_group_arg(args.groups)
    except ValueError as e:
        sys.exit(f"ERRO: {e}")
    entries, report = build(nums, cap=args.cap, skip_pc=args.no_pc, pc_cache_dir=args.pc_cache_dir)
    text = report_text(report, entries)
    note = f"Gerada com --groups {args.groups} --cap {args.cap}. " + text.splitlines()[0]
    Path(args.out).write_text(render_yaml(entries, note), encoding="utf-8")
    print(text)
    print(f"[build_watchlist] gravado em {args.out}")
    # Erra ALTO: colisao significa matcher furado. O artefato gravado ja esta limpo (as
    # cartas em colisao sairam), mas o run nao pode terminar como sucesso silencioso.
    if report["pc_collision"]:
        print(f"ERRO: {len(report['pc_collision'])} pagina(s) do PriceCharting com mais de "
              f"uma carta -- cartas removidas da watchlist; corrija o matcher e regenere.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
