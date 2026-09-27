#!/usr/bin/env python3
"""Gera `src/catalog/zh_identity.json`: impressão em chinês SIMPLIFICADO → carta EN.

Fonte: 52poke wiki via API (páginas dos produtos simplificados listadas nas navegações por
era + página de cada carta). Método e limites: `docs/CHINESE_IDENTITY.md` e o docstring de
`src/zh_identity.py`. Nenhum preço: só metadado público de impressão (set, número,
raridade, ilustrador, nome).

    python zh_catalog.py                          # catálogo completo → src/catalog/zh_identity.json
    python zh_catalog.py --report results/zh_identity_report.md
    python zh_catalog.py --only 星彩晶璃 --only 收集啦151\ 旅   # produtos escolhidos (teste rápido)

~1 requisição/s, lotes de 50 páginas; cache bruto em data/cache/52poke/ (local). Rodar só
em tarefa de catálogo (não faz parte do scan).
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sys

from src import chinese_scan, zh_identity as zi


def build(client: zi.WikiClient, only: list[str] | None = None, log=print) -> tuple[list[dict], dict, dict]:
    # 1) produtos simplificados (navegação por era)
    names: list[str] = []
    for nav in zi.NAV_TEMPLATES:
        for n in zi.nav_product_names(client.template_wikitext(f"PTCG版本导航/{nav}")):
            if n not in names:
                names.append(n)
    if only:
        names = [n for n in names if n in only] or list(only)
    log(f"produtos simplificados: {len(names)}")
    pages = client.pages([f"{n}（TCG）" for n in names])
    set_pages: list[zi.SetPage] = []
    for n in names:
        p = pages.get(f"{n}（TCG）") or {}
        if p.get("missing"):
            log(f"  produto sem página: {n}")
            continue
        sp = zi.parse_set_page(p["title"], p["wikitext"])
        if sp.entries:
            set_pages.append(sp)
    log(f"produtos com lista de cartas: {len(set_pages)} · entradas: {sum(len(s.entries) for s in set_pages)}")

    # 2) páginas das cartas (lotes de 50; a API resolve redirecionamento/variante)
    titles = []
    for sp in set_pages:
        for e in sp.entries:
            t = zi.card_page_title(e)
            if t and t not in titles:
                titles.append(t)
    log(f"páginas de carta a ler: {len(titles)}")
    fetched = client.pages(titles)
    card_pages: dict[str, zi.CardPage | None] = {}
    missing = []
    for t in titles:
        p = fetched.get(t) or {}
        if p.get("missing"):
            card_pages[t] = None
            missing.append(t)
        else:
            card_pages[t] = zi.parse_card_page(p["title"], p["wikitext"])
    log(f"  páginas ausentes: {len(missing)}")

    # 3) sets EN citados nas páginas → nome Bulbapedia (langlink) → nome da watchlist
    en_exp = collections.Counter()
    for cp in card_pages.values():
        if cp:
            for r in cp.en_rows:
                if r.get("enexpansion"):
                    en_exp[r["enexpansion"]] += 1
    ll = client.pages([f"{n}（TCG）" for n in en_exp], langlinks=True)
    en_map: dict[str, dict] = {}
    for n in en_exp:
        p = ll.get(f"{n}（TCG）") or {}
        bulba = p.get("en")
        en_map[n] = {"bulbapedia": bulba, "rows": en_exp[n]}
    unresolved_exp = [n for n, v in en_map.items() if not v["bulbapedia"]]
    log(f"sets EN citados: {len(en_map)} · sem langlink: {len(unresolved_exp)}")

    def resolve(exp_zh: str, en_no: str | None) -> tuple[str | None, bool]:
        bulba = (en_map.get(exp_zh) or {}).get("bulbapedia")
        if not bulba:
            return exp_zh, False
        return zi.to_watchlist_set(bulba, en_no)

    # 4) mapa JP→EN aprendido do corpus (semente: tabela curada do scan)
    seed = {k: set(v) for k, v in chinese_scan.ZH_SET_TO_EN.items()}
    jp_to_en = zi.learn_jp_to_en([cp for cp in card_pages.values() if cp], resolve, seed)

    # 5) junção
    rows: list[dict] = []
    seen = set()
    stats = collections.Counter()
    for sp in set_pages:
        for e in sp.entries:
            t = zi.card_page_title(e)
            cp = card_pages.get(t) if t else None
            code = sp.alt_code
            # produto sem `alt` (promos): código pela linha simplificada da própria carta
            if not code and cp:
                for r in cp.sc_rows:
                    if (r.get("cnexpansion") or "") == sp.name and r.get("cnicon"):
                        code = r["cnicon"]
                        break
            if not code:
                code = e.cn_total if e.cn_total and not e.cn_total.isdigit() else None
            if not code or not e.cn_no:
                stats["sem-chave"] += 1   # sem código ou sem número: não dá para consultar; fica fora
                continue
            linked = zi.link_entry(e, code, cp, resolve, jp_to_en, set_name=sp.name)
            key = (zi.norm_code(linked.cn_code), linked.cn_no, linked.cn_rar, linked.page, linked.en_no)
            if key in seen:
                continue
            seen.add(key)
            rows.append(linked.to_json())
            stats[linked.how or ("ambigua" if linked.ambiguous else "sem-par")] += 1
    rows.sort(key=lambda r: (zi.norm_code(r["cn_code"]), r.get("cn_no") or "", r.get("cn_rar") or ""))

    unresolved_sets = collections.Counter(r["en_set"] for r in rows if r.get("en_set_unresolved"))
    meta = {
        "generated_on": dt.date.today().isoformat(),
        "source": f"wiki.52poke.com via api.php — {zi.WIKI_LICENSE}",
        "products": len(set_pages), "card_pages": len(titles) - len(missing), "card_pages_missing": len(missing),
        "rows": len(rows), "how": dict(stats),
        "en_expansions": {k: v["bulbapedia"] for k, v in sorted(en_map.items())},
        "jp_to_en": {k: sorted(v) for k, v in sorted(jp_to_en.items())},
        "en_sets_unresolved": dict(unresolved_sets),
        "api_calls": client.calls,
    }
    report = {"missing_pages": missing, "unresolved_expansions": unresolved_exp,
              "ambiguous": [r for r in rows if r.get("ambiguous")], "products": [(s.title, s.alt_code, len(s.entries)) for s in set_pages]}
    return rows, meta, report


def render_report(rows: list[dict], meta: dict, report: dict) -> str:
    out = [f"# Catálogo de identidade simplificado → EN — {meta['generated_on']}", "",
           f"Fonte: {meta['source']}. Produtos: {meta['products']} · páginas de carta: {meta['card_pages']} "
           f"(ausentes: {meta['card_pages_missing']}) · linhas: {meta['rows']} · chamadas API: {meta['api_calls']}.", "",
           "## Como cada impressão foi ligada", "", "| como | linhas |", "|---|---:|"]
    for k, v in sorted(meta["how"].items(), key=lambda kv: -kv[1]):
        out.append(f"| {k} | {v} |")
    by_code = collections.defaultdict(collections.Counter)
    for r in rows:
        by_code[r["cn_code"]][r.get("how") or ("ambigua" if r.get("ambiguous") else "sem-par")] += 1
    out += ["", "## Por produto (código simplificado)", "", "| código | linhas | tc-jp | set+illus+rar | set+rar | illus+rar | ambígua | sem par |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for code, c in sorted(by_code.items()):
        out.append(f"| {code} | {sum(c.values())} | {c['tc-jp']} | {c['set+illus+rar']} | {c['set+rar']} | {c['illus+rar']} | {c['ambigua']} | {c['sem-par']} |")
    out += ["", "## Sets EN sem nome na watchlist (ficam com o nome Bulbapedia)", ""]
    out += [f"- {k}: {v} linhas" for k, v in sorted(meta["en_sets_unresolved"].items())] or ["- nenhum"]
    out += ["", "## Sets EN citados sem langlink EN", ""]
    out += [f"- {n}" for n in report["unresolved_expansions"]] or ["- nenhum"]
    out += ["", f"## Páginas de carta ausentes ({len(report['missing_pages'])})", ""]
    out += [f"- {t}" for t in report["missing_pages"][:200]] or ["- nenhuma"]
    out += ["", f"## Ambíguas ({len(report['ambiguous'])}) — alvo da conferência por imagem", ""]
    out += [f"- {r['cn_code']} {r['cn_no']} {r['cn_rar']} {r['zh_name']} → {' | '.join(r['ambiguous'])} ({r.get('note', '')})" for r in report["ambiguous"][:300]] or ["- nenhuma"]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=zi.CATALOG_PATH)
    ap.add_argument("--report", default=None, help="markdown com funil da junção, ausentes e ambíguas (local)")
    ap.add_argument("--cache", default=os.path.join("data", "cache", "52poke"))
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--only", action="append", help="nome do produto simplificado (repetível)")
    a = ap.parse_args(argv)
    client = zi.WikiClient(sleep_s=a.sleep, cache_dir=a.cache)
    rows, meta, report = build(client, a.only)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("{\n\"_meta\": " + json.dumps(meta, ensure_ascii=False, indent=1) + ",\n\"rows\": [\n")
        fh.write(",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows))
        fh.write("\n]}\n")
    print(f"{a.out}: {len(rows)} linhas · como: {meta['how']}")
    if a.report:
        os.makedirs(os.path.dirname(a.report) or ".", exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write(render_report(rows, meta, report))
        print(f"relatório: {a.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
