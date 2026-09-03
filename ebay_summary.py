"""Ferramenta CANONICA de entrega do scan eBay (espelho do comc_summary.py).

Le o artefato JSON gravado pelo `main.py --out` e gera a tabela markdown de
entrega -- grava em `-o` (obrigatorio) e imprime no stdout. O agente cola o
`.md` VERBATIM no chat: nunca remontar tabela a mao, nunca dropar link.

Contrato da frota (nao negociavel):
- TODAS as linhas de TODOS os buckets (OPORTUNIDADE / REVISAR / SUSPEITO /
  REJEITADO com motivo) -- nunca amostra.
- Toda linha tem os DOIS links: `[oferta]` (anuncio eBay, onde comprar) e
  `[referência]` (pagina da carta no PriceCharting, onde validar; `[TCG]` so
  quando nao ha pagina PC). URLs lidas do JSON, NUNCA inventadas.
- Vereditos sao classificacao tecnica; nenhuma recomendacao de compra.

`--sensitivity 10,15,20` (modo diagnostico, padrao COMC): o MAIOR limiar e o
operacional (faixa >=20% = candidato comercial: OPORTUNIDADE / REVISAR+SUSPEITO);
as faixas abaixo (15-19,99%, 10-14,99%) sao so diagnostico -- NAO sao
oportunidade -- e saem com TODAS as linhas da faixa, status na coluna, mais uma
tabela de contagens por limiar. Faixa = coluna Desconto% (`discount_pct`).

Uso:
    python ebay_summary.py results/last_scan.json -o results/ebay-2026-09-03.md \
        [--sensitivity 10,15,20]
"""
import argparse
import io
import json
import os
import sys

from src.report import funnel_lines, render_rejected_table, render_rows_table, sort_rows

VERDICTS = ("OPORTUNIDADE", "REVISAR", "SUSPEITO", "REJEITADO")

SECTION_TITLES = {
    "OPORTUNIDADE": "## 🟢 OPORTUNIDADE",
    "REVISAR": "## ⚠️ REVISAR (validar manualmente)",
    "SUSPEITO": "## 🚨 SUSPEITO (margem alta demais — validar)",
    "REJEITADO": "## ⛔ REJEITADO",
}
EMPTY_BUCKET = "_Nenhuma linha neste bucket._"

FOOTER = (
    "_Status: OPORTUNIDADE = passou em todas as validações; REVISAR = conferir "
    "manualmente (`vendas<3(n=…)` = mediana com só 1–2 vendas comparáveis; "
    "`coluna÷vendas(c)` = coluna informativa do PriceCharting >30% longe da mediana; "
    "`ref-desalinhada` = referência longe da mediana dos anúncios; divergência PC×TCG); "
    "SUSPEITO = ROI acima do teto de suspeita (bom demais = conferir carta/nota/vendedor); "
    "REJEITADO = motivo na coluna. `baixa-liquidez(365d)` é nota, não muda o status. "
    "`PC vendas <nota|LP> (n=…, mês..mês)` = mediana de vendas concluídas da mesma carta, "
    "variante, certificadora e nota (ou LP explícito); `TCG market` = TCGplayer market "
    "(raw NM). Link [referência] = página da carta no PriceCharting também para raw. "
    "Desconto% = (ref − eBay)/ref; Spread$ = ref − eBay (bruto, sem taxas, sem frete); "
    "ROI bruto% = spread/eBay. Vend = confiança do vendedor/anúncio (0–100), separada da "
    "margem. Ranking: ROI bruto → desconto % → spread US$ → popularidade do Pokémon. "
    "Só preço fixo, só item nos EUA. O scanner reporta dados; não é recomendação de compra._"
)


# ── faixas de sensibilidade (portado do comc_summary.py) ────────────────────────

def parse_sensitivity(text):
    """"10,15,20" -> [10, 15, 20]: inteiros positivos, estritamente crescentes (o
    maior e o limiar operacional). Qualquer outra coisa e erro de argumento."""
    try:
        vals = [int(p.strip()) for p in str(text).split(",") if p.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--sensitivity espera inteiros separados por vírgula, ex. 10,15,20 "
            f"(recebi {text!r})") from exc
    if not vals or any(v <= 0 for v in vals) or any(b <= a for a, b in zip(vals, vals[1:])):
        raise argparse.ArgumentTypeError(
            f"--sensitivity espera inteiros positivos em ordem crescente, ex. 10,15,20 "
            f"(recebi {text!r})")
    return vals


def _discount(row):
    try:
        return float(row.get("discount_pct") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _pct_br(value):
    """19.99 -> "19,99"; 20 -> "20" (virgula decimal, sem zeros a toa)."""
    txt = f"{value:.2f}".rstrip("0").rstrip(".")
    return txt.replace(".", ",")


def sensitivity_bands(thresholds):
    """[10, 15, 20] -> [(20, None), (15, 20), (10, 15)]: faixas [lo, hi) da maior
    para a menor; a primeira (hi=None) e a operacional."""
    asc = sorted(thresholds)
    bands = [(asc[-1], None)]
    for lo, hi in zip(reversed(asc[:-1]), reversed(asc[1:])):
        bands.append((lo, hi))
    return bands


def _in_band(row, lo, hi):
    d = _discount(row)
    return d >= lo and (hi is None or d < hi)


def sensitivity_counts(by_verdict, thresholds):
    """Tabela `| Limiar | OPORTUNIDADE | REVISAR/SUSPEITO | Total |` acumulada."""
    lines = ["| Limiar | OPORTUNIDADE | REVISAR/SUSPEITO | Total |",
             "| --- | --- | --- | --- |"]
    for t in sorted(thresholds, reverse=True):
        n_ok = sum(1 for r in by_verdict["OPORTUNIDADE"] if _discount(r) >= t)
        n_rev = sum(1 for r in by_verdict["REVISAR"] + by_verdict["SUSPEITO"]
                    if _discount(r) >= t)
        lines.append(f"| ≥{t}% | {n_ok} | {n_rev} | {n_ok + n_rev} |")
    return lines


# ── baldes, cobertura, cabecalho ────────────────────────────────────────────────

def split_verdicts(rows):
    """Rows por veredito, cada balde na ordem do ranking; veredito estranho
    vai para REVISAR (nunca dropar linha)."""
    by_verdict = {v: [] for v in VERDICTS}
    for row in rows:
        verdict = row.get("verdict")
        if verdict not in by_verdict:
            verdict = "REVISAR"
        by_verdict[verdict].append(row)
    return {v: sort_rows(b) for v, b in by_verdict.items()}


def _has_reference(row):
    return row.get("fair_value") is not None


def coverage_line(rows):
    """Cobertura de referencia: honestidade sobre a fonte de cada linha (so
    conta rows cuja margem USOU uma referencia; o resto e 'sem referência')."""
    refd = [r for r in rows if _has_reference(r)]

    def src(r):
        return str(r.get("ref_source") or r.get("ref_kind") or "")

    slab = sum(1 for r in refd if src(r) == "pricecharting-sales")
    raw_tcg = sum(1 for r in refd if src(r) == "tcgplayer")
    raw_lp = sum(1 for r in refd if src(r) == "pricecharting-sales-lp")
    raw_pc = sum(1 for r in refd if src(r) == "pricecharting")
    no_ref = len(rows) - len(refd)
    return (f"Cobertura de referência: {slab} slabs (mediana de vendas PC) · "
            f"{raw_tcg} raw NM c/ TCGplayer market · {raw_lp} raw LP (vendas LP PC) · "
            f"{raw_pc} raw só PriceCharting (fallback rotulado) · {no_ref} sem referência")


def _section(title, rows, rejected=False):
    lines = [title, ""]
    if rows:
        lines.append(render_rejected_table(rows) if rejected else render_rows_table(rows))
    else:
        lines.append(EMPTY_BUCKET)
    lines.append("")
    return lines


def _header(meta, rows, by_verdict, sensitivity):
    cfg = meta.get("config") or {}
    date = (meta.get("timestamp") or "")[:10] or "?"
    scope = f" · grupo `{meta['group']}`" if meta.get("group") else ""
    modes = []
    allowed = cfg.get("allowed_grades") or []
    if allowed:
        modes.append(f"funil restrito a {' + '.join(allowed)} (--grades)")
    if meta.get("include_raw"):
        modes.append("raw incluído (--include-raw: NM = TCG market; LP = vendas LP)")
    if meta.get("trusted_mode"):
        modes.append("modo confiável (--confiavel)")
    min_discount = cfg.get("min_discount_percent")
    if min_discount is None:
        legacy = cfg.get("min_gross_margin_percent")
        min_discount = (f"? (JSON antigo: gate era ROI bruto {legacy}%)"
                        if legacy is not None else "?")
    graded = cfg.get("graded_allow") or []
    counts = " · ".join(f"{len(by_verdict[v])} {v}" for v in VERDICTS)
    lines = [
        f"# Scan eBay — {date}",
        "",
        f"- Watchlist: {meta.get('watchlist_count', '?')} carta(s){scope}"
        + (f" · {' · '.join(modes)}" if modes else ""),
        f"- Parâmetros: desconto mínimo {min_discount}% · piso US${cfg.get('min_price_usd', '?')}"
        f" · só preço fixo · só item nos EUA · slabs aceitos: "
        f"{', '.join(graded) if graded else '—'}",
        f"- Vereditos: {counts}",
        f"- {coverage_line(rows)}",
    ]
    funnel = meta.get("funnel") or {}
    if funnel:
        lines.append("- Funil: " + " · ".join(funnel_lines(funnel)))
    if meta.get("aborted"):
        lines.append("- ⚠️ RUN ABORTADO antes do fim: as cartas restantes NÃO foram varridas.")
    if sensitivity:
        operational = max(sensitivity)
        lines.append(f"- Modo diagnóstico: scan com desconto mínimo {min_discount}% · "
                     f"limiar operacional {operational}% (faixas abaixo NÃO são oportunidade)")
        try:
            scan_min = float(min_discount)
        except (TypeError, ValueError):
            scan_min = None
        if scan_min is not None and scan_min > min(sensitivity):
            lines.append(f"- ⚠️ O scan rodou com desconto mínimo {_pct_br(scan_min)}% > menor "
                         f"limiar {min(sensitivity)}%: faixas abaixo de {_pct_br(scan_min)}% "
                         "ficam vazias por construção (re-rode com --min-discount "
                         f"{min(sensitivity)} para enxergá-las).")
        lines.append("")
        lines.extend(sensitivity_counts(by_verdict, sensitivity))
    lines.append("- Vereditos são classificação técnica — decisão de capital é do operador.")
    lines.append("")
    return lines


def _sensitivity_sections(by_verdict, thresholds):
    lines = []
    ok = by_verdict["OPORTUNIDADE"]
    review = by_verdict["REVISAR"] + by_verdict["SUSPEITO"]
    for lo, hi in sensitivity_bands(thresholds):
        if hi is None:
            lines += _section(f"## 🟢 ≥{lo}% — candidato comercial (sujeito às demais validações)",
                              sort_rows([r for r in ok if _in_band(r, lo, hi)]))
            lines += _section(f"## ⚠️ ≥{lo}% — REVISAR / SUSPEITO (validar manualmente)",
                              sort_rows([r for r in review if _in_band(r, lo, hi)]))
        else:
            rows = sort_rows([r for r in ok + review if _in_band(r, lo, hi)])
            lines += _section(f"## 🔬 Diagnóstico {lo}–{_pct_br(hi - 0.01)}% — NÃO é oportunidade",
                              rows)
    lines += _section("## ⛔ REJEITADO (todas as faixas)", by_verdict["REJEITADO"], rejected=True)
    return lines


def _verdict_sections(by_verdict):
    lines = []
    for verdict in VERDICTS:
        lines += _section(SECTION_TITLES[verdict], by_verdict[verdict],
                          rejected=(verdict == "REJEITADO"))
    return lines


def build_markdown(payload, sensitivity=None):
    """JSON do scan -> markdown de entrega (todas as linhas, todos os buckets)."""
    meta = payload.get("meta") or {}
    rows = payload.get("rows") or []
    by_verdict = split_verdicts(rows)
    lines = _header(meta, rows, by_verdict, sensitivity)
    if sensitivity:
        lines += _sensitivity_sections(by_verdict, sensitivity)
    else:
        lines += _verdict_sections(by_verdict)
    lines.append(FOOTER)
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser(
        description="Gera a entrega canonica (markdown) do scan eBay")
    ap.add_argument("scan_json", help="artefato JSON do scan (main.py --out)")
    ap.add_argument("-o", "--output", required=True,
                    help="arquivo .md de saida (obrigatorio)")
    ap.add_argument("--sensitivity", type=parse_sensitivity, default=None, metavar="10,15,20",
                    help="modo diagnostico: limiares de desconto crescentes; o maior e o "
                         "operacional, os demais viram faixas 'NAO e oportunidade'")
    args = ap.parse_args(argv)

    with open(args.scan_json, encoding="utf-8-sig") as f:
        payload = json.load(f)

    md = build_markdown(payload, sensitivity=args.sensitivity)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\n[gravado em {args.output}]", file=sys.stderr)


if __name__ == "__main__":
    main()
