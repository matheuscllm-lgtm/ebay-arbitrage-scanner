"""Validacao MINIMA da coluna informativa "Longo prazo" sobre o JSON de um scan.

Ideia (nao codigo) de `outlook/validate.py` do repo pokemon-longterm-outlook: uma
calibracao transversal (comparar cartas de hoje entre si) para saber se cada componente
do PERFIL acompanha o preco de mercado -- sem backtest fantasioso.

O que faz:
1. AGREGA por chave (carta, numero, nota) ANTES de qualquer estatistica: 11 anuncios do
   mesmo item contam 1 (senao seria pseudo-replicacao = contar o mesmo item varias vezes e
   inflar a estatistica). Por chave: mediana de `fair_value`, mediana do premio de nota
   (coluna PSA 10 / coluna RAW do PriceCharting) e os sinais crus da carta.
2. Exige n >= 30 chaves. Abaixo disso imprime "n insuficiente (k cartas)" e NAO inventa
   rho (Spearman = correlacao de postos: mede se "nota maior" acompanha "preco maior").
3. Com n >= 30: rho de B1 (personagem), B2 (raridade), B3 (supply), B5 (tendencia) e do
   PERFIL-sem-B4 contra (a) `fair_value` e (b) o premio PSA 10 / RAW. B4 (faixa de preco
   PSA 10) e EXCLUIDO: e derivado de preco, correlaciona-lo com preco seria circular.
   Rotulos: rho > 0.1 = OK · -0.1..0.1 = fraco · <= -0.1 = invertido. Os pontos por
   componente sao RECALCULADOS dos sinais crus pelas mesmas funcoes puras de
   `src/longterm.py` (nada e reinventado aqui).
4. Sanidade (so com n >= 30): LP1 acima de 30% das chaves exige explicacao; no caminho
   `slab_strategy` desta rodada 0% de LP1 e ESPERADO (teto LP2*, `ref-desalinhada` em n/d).
5. Cobertura por sinal (qual campo faltou, em qual caminho) e cobertura media das notas.
6. Snapshot datado em CSV (`results/snapshots/longterm_AAAA-MM-DD.csv`, local, gitignored):
   insumo de um backtest futuro, so com >= 2 snapshots com >= 21 dias de intervalo.

Frases obrigatorias do relatorio: "calibracao transversal nao e prova de valorizacao
futura" (valorizacao = subida de preco ao longo do tempo) e "rho calculado sobre chaves
(carta, numero, nota), nao sobre anuncios". Nada aqui recomenda compra nem muda o scan.

Uso:
    python longterm_validate.py results/lt-smoke-g3.json
    python longterm_validate.py results/x.aborted.json --snapshot-dir results/snapshots --min-keys 30
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src import longterm

RHO_OK = 0.1          # acima: componente acompanha o preco
RHO_INVERTED = -0.1   # abaixo ou igual: invertido
MIN_KEYS_DEFAULT = 30
MIN_PAIRS = 3         # pares (componente, preco) para calcular rho
LP1_SHARE_MAX = 30.0  # % de LP1 acima disto exige explicacao

COMPONENTS = (("B1", "personagem (rank)"), ("B2", "raridade"), ("B3", "supply"),
              ("B5", "tendência 12 m"), ("PERFIL-sem-B4", "perfil sem a faixa de preço"))
COVERAGE_SIGNALS = ("pokemon_rank", "rarity_raw", "year", "era", "psa10_col", "raw_col",
                    "psa10_sales_pm", "trend_12m_pct", "ref_source", "dispersion_pct",
                    "ask_ratio")
TIERS = ("LP1", "LP2", "LP3", "LP4", "n/d")

SENTENCE_KEYS = "ρ calculado sobre chaves (carta, número, nota), não sobre anúncios"
SENTENCE_NO_PROOF = ("calibração transversal não é prova de valorização futura "
                     "(valorização = subida de preço ao longo do tempo)")


# --- estatistica pura -----------------------------------------------------------

def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _ranks(values):
    """Postos 1..n com posto medio nos empates."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def spearman(a, b):
    """rho de Spearman (correlacao de postos, -1..1): Pearson sobre os postos, empates com
    posto medio. Sem variancia em um dos lados (ou < 2 pares) -> NaN (nunca 0 inventado)."""
    n = len(a)
    if n != len(b) or n < 2:
        return float("nan")
    ra, rb = _ranks(list(a)), _ranks(list(b))
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va <= 0 or vb <= 0:
        return float("nan")
    return cov / math.sqrt(va * vb)


def flag(rho):
    """Rotulo do rho: > 0.1 OK · -0.1..0.1 fraco · <= -0.1 invertido · NaN/None -> n/d."""
    if rho is None or rho != rho:
        return "n/d"
    if rho > RHO_OK:
        return "✅"
    if rho > RHO_INVERTED:
        return "⚠️ fraco"
    return "❌ invertido"


def _median(values):
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


# --- agregacao por chave ----------------------------------------------------------

def _tier_bucket(tier):
    text = str(tier or "").strip().rstrip("*")
    return text if text in TIERS[:4] else "n/d"


def aggregate_by_key(rows):
    """{(carta, numero, nota): {...}} -- mediana de `fair_value` e do premio PSA 10/RAW por
    chave, sinais crus da carta (primeiro valor nao nulo por campo), classe mais comum entre
    os anuncios da chave, `n_listings` e se a chave veio do caminho da politica."""
    groups = {}
    for row in rows or []:
        key = (str(row.get("card") or ""), str(row.get("number") or ""), str(row.get("grade") or ""))
        g = groups.setdefault(key, {"n_listings": 0, "fair_values": [], "premiums": [],
                                    "trends": [], "tiers": [], "signals": {}, "policy": False,
                                    "coverage": []})
        g["n_listings"] += 1
        fv = _num(row.get("fair_value"))
        if fv is not None:
            g["fair_values"].append(fv)
        signals = row.get("longterm_signals") or {}
        for name, value in signals.items():
            if value is not None and g["signals"].get(name) is None:
                g["signals"][name] = value
        psa10, raw = _num(signals.get("psa10_col")), _num(signals.get("raw_col"))
        if psa10 and raw and raw > 0:
            g["premiums"].append(psa10 / raw)
        trend = _num(signals.get("trend_12m_pct"))
        if trend is None:
            trend = _num(row.get("trend_12m_pct"))
        if trend is not None:
            g["trends"].append(trend)
        g["tiers"].append(_tier_bucket(row.get("longterm_tier")))
        if row.get("strategy"):
            g["policy"] = True
        g["coverage"].append(str(row.get("longterm_coverage") or ""))
    out = {}
    for key, g in groups.items():
        out[key] = {
            "n_listings": g["n_listings"],
            "fair_value": _median(g["fair_values"]),
            "premium": _median(g["premiums"]),
            "trend_12m_pct": _median(g["trends"]),
            "tier": Counter(g["tiers"]).most_common(1)[0][0] if g["tiers"] else "n/d",
            "signals": g["signals"],
            "policy": g["policy"],
            "coverage": g["coverage"],
        }
    return out


def component_points(entry):
    """B1, B2, B3, B5 da chave, RECALCULADOS dos sinais crus pelas funcoes puras de
    src/longterm.py; B4 nao entra (derivado de preco = circular)."""
    s = entry.get("signals") or {}
    age = s.get("age_years")
    if age is None and s.get("year") is not None:
        try:
            age = datetime.now(timezone.utc).year - int(s["year"])
        except (TypeError, ValueError):
            age = None
    points = {
        "B1": longterm.character_points(s.get("pokemon_rank")),
        "B2": longterm.rarity_points(s.get("rarity_raw"), s.get("era")),
        "B3": longterm.supply_points(age, bool(s.get("heavy_reprint"))),
        "B5": longterm.trend_points(entry.get("trend_12m_pct")),
    }
    available = [v for v in points.values() if v is not None]
    points["PERFIL-sem-B4"] = (round(sum(available) / (longterm.MAX_POINTS_PER_COMPONENT * len(available)) * 100.0, 1)
                               if len(available) >= 3 else None)
    return points


def _rho_cell(pairs):
    """'+0.93 ✅ (n=30)' ou 'n/d (...)' -- nunca um numero inventado."""
    if len(pairs) < MIN_PAIRS:
        return f"n/d (n={len(pairs)} < {MIN_PAIRS} pares)"
    rho = spearman([a for a, _ in pairs], [b for _, b in pairs])
    if rho != rho:
        return f"n/d (sem variação; n={len(pairs)})"
    return f"{rho:+.2f} {flag(rho)} (n={len(pairs)})"


def _parse_coverage(text):
    """'4/5·9/11' -> (4, 9) ou None (só os numeradores; os denominadores vêm de
    `longterm.PROFILE_COMPONENTS` / `longterm.FRAGILITY_FLAGS` na hora de imprimir)."""
    try:
        profile, fragility = str(text).split("·")
        return int(profile.split("/")[0]), int(fragility.split("/")[0])
    except (ValueError, AttributeError):
        return None


# --- relatorio --------------------------------------------------------------------

def calibration_report(rows, min_keys=MIN_KEYS_DEFAULT):
    rows = list(rows or [])
    keys = aggregate_by_key(rows)
    n_keys = len(keys)
    policy_keys = sum(1 for e in keys.values() if e["policy"])
    legacy_keys = n_keys - policy_keys
    lines = ["# Longo prazo — validação mínima (calibração transversal, não é backtest)", ""]
    lines.append(f"n = {n_keys} chaves (carta, número, nota) sobre {len(rows)} anúncios · "
                 f"caminho: {legacy_keys} legado · {policy_keys} política (slab_strategy)")

    # distribuicao de classes por chave (LP2* conta como LP2)
    dist = Counter(e["tier"] for e in keys.values())
    lines.append("Distribuição por classe (chaves): " + " · ".join(f"{dist.get(t, 0)} {t}" for t in TIERS))

    if n_keys < min_keys:
        lines.append(f"n insuficiente ({n_keys} cartas): ρ não calculado (mínimo {min_keys} chaves); "
                     "nenhum número de correlação é inventado abaixo disso.")
    else:
        lines += ["", "| Componente | ρ vs fair_value (mediana por chave) | ρ vs prêmio PSA 10 ÷ RAW |",
                  "|---|---|---|"]
        for code, label in COMPONENTS:
            fv_pairs, pr_pairs = [], []
            for e in keys.values():
                pts = component_points(e).get(code)
                if pts is None:
                    continue
                if e["fair_value"] is not None:
                    fv_pairs.append((pts, e["fair_value"]))
                if e["premium"] is not None:
                    pr_pairs.append((pts, e["premium"]))
            lines.append(f"| {code} {label} | {_rho_cell(fv_pairs)} | {_rho_cell(pr_pairs)} |")
        lines += ["", "B4 excluído da correlação: a faixa de preço PSA 10 é derivada do próprio preço — "
                      "correlacioná-la com fair_value seria circular.",
                  "Rótulos: ρ > 0.1 ✅ · −0.1..0.1 ⚠️ fraco · ≤ −0.1 ❌ invertido; componente invertido "
                  "não vai ao PR sem nota explícita."]
        lp1_share = dist.get("LP1", 0) / n_keys * 100.0
        sanity = f"Sanidade: LP1 = {lp1_share:.1f}% das chaves"
        if lp1_share > LP1_SHARE_MAX:
            sanity += f" — acima de {LP1_SHARE_MAX:.0f}%: exige explicação (sem validação, isto é suspeito)"
        lines += ["", sanity]
    if policy_keys:
        lines.append("0% de LP1 é esperado no caminho slab_strategy nesta rodada: teto LP2* porque "
                     "`ref-desalinhada` fica em n/d (`asks = {}`, decisão documentada do operador).")

    # cobertura por sinal (qual campo faltou, em qual caminho) e cobertura media das notas
    lines += ["", "Cobertura por sinal (chaves com dado / chaves do caminho):"]
    for name in COVERAGE_SIGNALS:
        by_path = {"legado": [0, 0], "política": [0, 0]}
        for e in keys.values():
            path = "política" if e["policy"] else "legado"
            by_path[path][1] += 1
            if (e["signals"] or {}).get(name) is not None:
                by_path[path][0] += 1
        parts = [f"{path} {have}/{total}" for path, (have, total) in by_path.items() if total]
        lines.append(f"- {name}: " + (" · ".join(parts) if parts else "0/0"))
    profiles, fragilities = [], []
    for e in keys.values():
        for text in e["coverage"]:
            parsed = _parse_coverage(text)
            if parsed:
                profiles.append(parsed[0])
                fragilities.append(parsed[1])
    if profiles:
        # Denominadores vindos das listas do módulo: um "5"/"10" escrito aqui passaria
        # a mentir no relatório assim que um componente ou uma flag entra ou sai.
        lines.append("Cobertura média (anúncios com a coluna): "
                     f"perfil {statistics.mean(profiles):.1f}/{len(longterm.PROFILE_COMPONENTS)} · "
                     f"fragilidade {statistics.mean(fragilities):.1f}/{len(longterm.FRAGILITY_FLAGS)}")
    else:
        lines.append("Cobertura média: n/d (nenhum anúncio com a coluna preenchida)")

    lines += ["", f"Nota: {SENTENCE_KEYS}; {SENTENCE_NO_PROOF}. Régua = {longterm.CALIBRATION_NOTE}. "
                  "Nada aqui recomenda compra nem altera veredito, gate ou ranking."]
    return "\n".join(lines)


# --- snapshot ---------------------------------------------------------------------

SNAPSHOT_FIELDS = ("date", "card", "number", "grade", "price", "fair_value", "perfil",
                   "fragilidade", "classe", "coberturas", "fontes", "caminho", "trend_12m_pct")


def _nd(value):
    return "n/d" if value is None or value == "" else value


def write_snapshot(rows, snapshot_dir, day=None):
    """CSV datado (um anuncio por linha) para backtest futuro; None -> 'n/d', nunca 0."""
    day = day or datetime.now(timezone.utc).date().isoformat()
    path = Path(snapshot_dir) / f"longterm_{day}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SNAPSHOT_FIELDS)
        writer.writeheader()
        for row in rows or []:
            signals = row.get("longterm_signals") or {}
            sources = (f"ref={_nd(signals.get('ref_source'))};trend={_nd(signals.get('trend_source'))};"
                       f"disp={_nd(signals.get('dispersion_source'))}")
            writer.writerow({
                "date": day, "card": row.get("card", ""), "number": row.get("number", ""),
                "grade": row.get("grade", ""), "price": _nd(row.get("price")),
                "fair_value": _nd(row.get("fair_value")),
                "perfil": _nd(row.get("longterm_profile")),
                "fragilidade": _nd(row.get("longterm_fragility")),
                "classe": _nd(row.get("longterm_tier")),
                "coberturas": _nd(row.get("longterm_coverage")), "fontes": sources,
                "caminho": "slab_strategy" if row.get("strategy") else "legado",
                "trend_12m_pct": _nd(signals.get("trend_12m_pct", row.get("trend_12m_pct"))),
            })
    return str(path)


def _scan_day(meta):
    """Data do snapshot = data do `meta.timestamp` do scan (nao a data de hoje)."""
    stamp = str((meta or {}).get("timestamp") or "")[:10]
    try:
        return datetime.strptime(stamp, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def main(argv=None):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="Validação mínima da coluna Longo prazo sobre o JSON de um scan")
    ap.add_argument("scan_json", help="artefato JSON do scan (main.py --out; .json ou .aborted.json)")
    ap.add_argument("--snapshot-dir", default=os.path.join("results", "snapshots"),
                    help="pasta do snapshot CSV datado (local, gitignored)")
    ap.add_argument("--min-keys", type=int, default=MIN_KEYS_DEFAULT,
                    help="mínimo de chaves (carta, número, nota) para calcular ρ")
    args = ap.parse_args(argv)
    with open(args.scan_json, encoding="utf-8-sig") as f:
        payload = json.load(f)
    rows = payload.get("rows") or []
    meta = payload.get("meta") or {}
    print(calibration_report(rows, min_keys=args.min_keys))
    if meta.get("aborted"):
        print("\nAtenção: `meta.aborted` = True — resultado PARCIAL do scan; a calibração cobre só o que foi coletado.")
    path = write_snapshot(rows, args.snapshot_dir, day=_scan_day(meta))
    print(f"\nSnapshot gravado (local, não versionado): {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
