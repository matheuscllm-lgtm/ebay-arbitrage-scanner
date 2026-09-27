"""Consolida os JSONs do modo chinês (um por grupo/lote) e imprime a análise independente
da tese em markdown: agregados por idioma, funil do crivo de razão e páginas chinesas mais
líquidas. Sem linha por anúncio — a entrega por linha é o `ebay_summary.py`.

    python chinese_thesis.py results/chinese-g*.json -o results/analise_tese.md
    python chinese_thesis.py results/chinese-g*.json --merge-out results/chinese-all.json
    python ebay_summary.py results/chinese-all.json -o results/chinese-all.md --compact

Tudo é re-pontuado com a régua vigente (`chinese_scan.rescore`) antes de agregar, então um
JSON antigo sai com a classificação de hoje. Resultado (preço, carta) nunca vai ao repositório.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import chinese_scan as cs  # noqa: E402

LANG_LABEL = {"ZH-HANS": "simplificado", "ZH-HANT": "tradicional", "ZH": "não especificado"}
LANGS = ("ZH-HANS", "ZH-HANT", "ZH")

# Etapas do funil de um anúncio que passou o crivo de razão, na ordem em que `classify`
# derruba: cada linha cai na PRIMEIRA etapa cujo motivo aparece em `reasons`.
FUNNEL_STEPS = (
    ("catálogo de impressões: a carta chinesa é OUTRA carta EN ou não tem par EN",
     ("catalogo-outra-carta", "catalogo-sem-par-en")),
    ("identidade: nome sem número EN e set chinês sem correspondência curada nem catálogo",
     ("match-nome", "match-nome-base", "set-zh-sem-correspondencia", "catalogo-ambiguo")),
    ("raridade não confirmada ou divergente", ("raridade-nao-confirmada", "raridade-divergente")),
    ("idioma não especificado no título", ("idioma-nao-especificado",)),
    ("página chinesa não encontrada / ambígua / teto", ("zh-",)),
    ("menos vendas PSA 10 em chinês que o mínimo (90 d)", ("evidencia-zh-insuficiente",)),
    ("set chinês é OUTRA carta (arte/set divergente)", ("set-zh-divergente",)),
    ("referência EN pela coluna do site (<3 vendas)", ("ref-en-coluna-PC",)),
)


def load_payloads(paths: list[str]) -> list[dict]:
    files: list[str] = []
    for p in paths:
        hits = sorted(glob.glob(p))
        files += hits or [p]
    out = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        if (d.get("meta") or {}).get("kind") != cs.KIND:
            raise SystemExit(f"{f}: meta.kind != {cs.KIND!r} — não é JSON do modo chinês")
        d["meta"]["_file"] = f
        out.append(d)
    if not out:
        raise SystemExit("nenhum JSON de entrada")
    return out


def merge(payloads: list[dict], today: str | None = None) -> dict:
    """Um payload só, com meta consolidada (funil somado, grupos listados) e rows concatenadas."""
    metas = [p["meta"] for p in payloads]
    funnel: collections.Counter = collections.Counter()
    for m in metas:
        funnel.update(m.get("funnel") or {})

    def _grp(m):
        g = str(m.get("group") or "?")
        return (int(g) if g.isdigit() else 10**6, g)

    groups = []
    for m in sorted(metas, key=_grp):
        g = str(m.get("group") or "?")
        if g not in groups:
            groups.append(g)
    latest = max(str(m.get("timestamp") or "") for m in metas)
    stamp = today or latest[:10]
    # Lotes do mesmo grupo (--max-cards/--card-offset) adiam um ao outro: o adiado real do
    # consolidado é o que foi agendado e não concluído, não a soma dos adiados de cada lote.
    scheduled = sum(int(m.get("scheduled") or 0) for m in metas)
    completed = sum(int((m.get("selection") or {}).get("cards_completed") or 0) for m in metas)
    sel = {"cards_completed": completed, "cards_deferred": max(0, scheduled - completed)}
    meta = {
        "kind": cs.KIND,
        "policy_version": metas[0].get("policy_version"),
        "timestamp": f"{latest} (consolidado de {len(metas)} runs, {stamp})",
        "group": ", ".join(groups),
        "watchlist_count": sum(int(m.get("watchlist_count") or 0) for m in metas),
        "scheduled": scheduled,
        "params": metas[0].get("params") or {},
        "funnel": dict(funnel),
        "aborted": any(bool(m.get("aborted")) for m in metas),
        "selection": sel,
        "outlook_available": all(bool(m.get("outlook_available")) for m in metas),
        "sources": [m.get("_file") for m in metas],
    }
    rows = []
    for p in payloads:
        for r in p["rows"]:
            r = dict(r)
            r["_group"] = p["meta"].get("group")
            rows.append(r)
    return cs.rescore({"meta": meta, "rows": rows})


def _q(vals, p):
    vals = sorted(v for v in vals if v is not None)
    return vals[min(len(vals) - 1, int(p * (len(vals) - 1)))] if vals else None


def _pct(part, whole):
    return f"{100 * part / whole:.0f}%" if whole else "n/d"


def ratio_funnel(rows: list[dict], lang: str, min_ratio: float) -> list[tuple[str, int, int]]:
    """(etapa, entram, saem) para os pares do idioma com referência EN por vendas e razão ≥ corte."""
    rem = [r for r in rows if not r.get("exclusive") and r.get("language") == lang
           and (r.get("en_ref") or {}).get("source") == "vendas"
           and (r.get("ratio") or 0) >= min_ratio]
    out = []
    for label, prefixes in FUNNEL_STEPS:
        keep, drop = [], []
        for r in rem:
            hit = any(str(x).startswith(pfx) for x in (r.get("reasons") or []) for pfx in prefixes)
            (drop if hit else keep).append(r)
        out.append((label, len(rem), len(drop)))
        rem = keep
    out.append(("candidatas", len(rem), 0))
    return out


def thesis_markdown(payload: dict) -> str:
    rows = payload["rows"]
    meta = payload.get("meta") or {}
    params = meta.get("params") or cs.DEFAULT_PARAMS
    min_ratio = float(params.get("min_ratio", cs.DEFAULT_PARAMS["min_ratio"]))
    pairs = [r for r in rows if not r.get("exclusive")]
    excl = [r for r in rows if r.get("exclusive")]
    ok = [r for r in rows if (r.get("zh") or {}).get("status") == "ok"]
    buckets = dict(collections.Counter(r["bucket"] for r in rows))
    out = [f"# Análise independente da tese — modo chinês ({meta.get('timestamp', 'n/d')})", ""]
    out.append(f"Cobertura: grupos {meta.get('group', 'n/d')} = {(meta.get('selection') or {}).get('cards_completed', 'n/d')} "
               f"cartas EN consultadas · {len(rows)} anúncios PSA 10 em chinês avaliados ({len(pairs)} pares + {len(excl)} exclusivas) · "
               f"buckets: {buckets}.")
    out.append("")
    out.append("| Idioma (pares c/ ref EN por vendas) | Anúncios | Razão EN÷ZH p25 / p50 / p75 / p90 | "
               f"≥{min_ratio:g}× | <1× (chinês pede mais que a mediana EN) | Candidatas |")
    out.append("|---|---|---|---|---|---|")
    for lang in LANGS:
        sub = [r for r in pairs if r.get("language") == lang and (r.get("en_ref") or {}).get("source") == "vendas" and r.get("ratio")]
        rs = [r["ratio"] for r in sub]
        if not rs:
            continue
        ge = sum(1 for x in rs if x >= min_ratio)
        lt1 = sum(1 for x in rs if x < 1)
        out.append(f"| {LANG_LABEL[lang]} | {len(rs)} | {_q(rs, .25):.2f} / {_q(rs, .5):.2f} / {_q(rs, .75):.2f} / {_q(rs, .9):.2f} | "
                   f"{ge} ({_pct(ge, len(rs))}) | {lt1} ({_pct(lt1, len(rs))}) | {sum(1 for r in sub if r['bucket'] == 'candidata')} |")
    out.append("")
    out.append("| Evidência chinesa (páginas do PriceCharting) | Pares | Exclusivas |")
    out.append("|---|---|---|")

    def _marg(s):
        return [r["zh_margin_pct"] for r in s if r.get("zh_margin_pct") is not None]

    metrics = (
        ("anúncios com página chinesa encontrada", lambda s: str(len(s))),
        ("páginas únicas", lambda s: str(len({r["zh"]["url"] for r in s}))),
        ("vendas PSA 10 em 90 d por página (mediana)", lambda s: str(st.median([r["zh"]["n_sales_90d"] for r in s])) if s else "n/d"),
        ("margem bruta vs revenda chinesa (mediana)", lambda s: f"{st.median(_marg(s)):+.0f}%" if _marg(s) else "n/d"),
        ("anúncios com margem > 0 vs revenda chinesa", lambda s: (f"{_pct(sum(1 for x in _marg(s) if x > 0), len(_marg(s)))} de {len(_marg(s))}" if _marg(s) else "n/d")),
    )
    for label, fn in metrics:
        out.append(f"| {label} | {fn([r for r in ok if not r.get('exclusive')])} | {fn([r for r in ok if r.get('exclusive')])} |")
    out.append("")
    uniq: dict[str, dict] = {}
    for r in ok:
        uniq.setdefault(r["zh"]["url"], r)
    for lang in LANGS:
        u = [r for r in uniq.values() if r.get("language") == lang]
        if not u:
            continue
        tr = [r["zh"]["trend_observed_pct"] for r in u if r["zh"].get("trend_observed_pct") is not None]
        pop = [r["zh"]["pop_psa10"] for r in u if r["zh"].get("pop_psa10") is not None and (r["zh"].get("pop_total") or 0) >= cs.POP_TOTAL_MIN_TRUST]
        liq = [r for r in u if r["zh"]["n_sales_90d"] >= int(params.get("min_zh_sales", 3))]
        trend = "n/d" if not tr else f"{st.median(tr):+.0f}% (n={len(tr)}, {sum(1 for t in tr if t > 0)} positivas)"
        census = f"{len(pop)} páginas" + (f", pop PSA 10 mediana {st.median(pop):.0f}" if pop else "")
        out.append(f"- **{LANG_LABEL[lang]}**: {len(u)} páginas únicas · {len(liq)} com ≥{params.get('min_zh_sales', 3)} vendas PSA 10 em 90 d · "
                   f"tendência observada (mediana 90 d vs 90–365 d, só páginas com ≥3 vendas em cada janela): {trend} · "
                   f"censo PSA confiável (≥{cs.POP_TOTAL_MIN_TRUST} no total): {census}.")
    out.append("")
    out.append("Motivos mais comuns nas linhas ⚠️ validar: " + ", ".join(
        f"{k} ({v})" for k, v in collections.Counter(w for r in rows if r["bucket"] == "validar" for w in r.get("reasons") or []).most_common(8)) + ".")
    out.append("")
    out.append(f"## Funil do crivo (pares com referência EN por vendas e razão ≥ {min_ratio:g}×) — por que a razão sozinha não vira candidata")
    out.append("")
    for lang in LANGS:
        steps = ratio_funnel(rows, lang, min_ratio)
        if not steps or steps[0][1] == 0:
            continue
        out.append(f"**{LANG_LABEL[lang]}** — {steps[0][1]} anúncios passam o crivo de razão:")
        out.append("")
        out.append("| Etapa | Entram | Saem |")
        out.append("|---|---|---|")
        for label, n_in, n_out in steps:
            out.append(f"| {label} | {n_in} | {n_out if label != 'candidatas' else '—'} |")
        out.append("")
    top = sorted(uniq.values(), key=lambda r: -r["zh"]["n_sales_90d"])[:12]
    if top:
        out.append("| Páginas chinesas mais líquidas (vendas PSA 10 em 90 d) | Idioma | n/90 d | Mediana US$ | Tend. obs. | Pop10 | Menor anúncio US$ | Margem no menor |")
        out.append("|---|---|---|---|---|---|---|---|")
        for r in top:
            same = [x for x in ok if x["zh"]["url"] == r["zh"]["url"]]
            cheap = min(same, key=lambda x: x["listing"]["price"])
            z = r["zh"]
            trend_s = "n/d" if z.get("trend_observed_pct") is None else f"{z['trend_observed_pct']:+.0f}%"
            pop_s = z["pop_psa10"] if z.get("pop_psa10") is not None else "n/d"
            marg_s = "n/d" if cheap.get("zh_margin_pct") is None else f"{cheap['zh_margin_pct']:+.0f}%"
            url = (cheap["listing"].get("url") or "").split("?")[0]
            out.append(f"| [{z['url'].split('/game/')[-1]}]({z['url']}) | {LANG_LABEL.get(r.get('language'), r.get('language'))} | "
                       f"{z['n_sales_90d']} | {z['median_90d']:.2f} | {trend_s} | {pop_s} | [{cheap['listing']['price']:.2f}]({url}) | {marg_s} |")
    out.append("")
    out.append("Nenhuma recomendação de compra: agregados descrevem o mercado observado nos anúncios e páginas consultados, não o mercado inteiro.")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Consolida JSONs do modo chinês e imprime a análise da tese (markdown).")
    ap.add_argument("inputs", nargs="+", help="JSONs do chinese_scan.py (aceita glob, ex.: results/chinese-g*.json)")
    ap.add_argument("-o", "--out", help="grava o markdown aqui (além de imprimir)")
    ap.add_argument("--merge-out", help="grava o JSON consolidado (re-pontuado) para o ebay_summary.py")
    a = ap.parse_args(argv)
    payload = merge(load_payloads(a.inputs))
    if a.merge_out:
        Path(a.merge_out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.merge_out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
    md = thesis_markdown(payload)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
