"""Ponte offline entre a base parcial (3.490 referências EN) e o catálogo completo.

`ID EN` da base parcial é o número da linha (1..3490), não o `ID PokeData` do
catálogo: dos 1.785 inteiros que coincidem, só 2 têm o mesmo set e número.
Esta ponte usa metadados (set + número impresso + nome PokeData) e nunca a
igualdade de inteiros. Toda referência sai no resultado, inclusive sem match.

Uso: python research/pokedata/bridge_partial_ids.py [-o ponte.csv]
O CSV contém só identidade (IDs, set, número, nome); nunca preços.
Status: `unico` = exatamente 1 ID; `ambiguo` = 2+ IDs (variantes homônimas,
exige revisão); `sem_match` = nenhum. Nada aqui confirma arte ou impressão.
"""
import argparse
import csv
import io
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG_MEMBER = "pokedata_crossref/output/PokeData_catalogo_correspondencia.xlsx"
PARTIAL = ROOT / "inputs/PokeData_correspondencias_JP_CHS_CHT_parcial_recebido.xlsx"
FIELDS = ["id_en_parcial", "carta_parcial", "codigo_parcial", "set_parcial",
          "metodo", "status", "ids_pokedata", "numeros_impressos_catalogo", "nomes_catalogo"]


_GENDER = (("\u2640", " female "), ("\u2642", " male "))
_NIDORAN_ALIAS = re.compile(r"\bnidoran\s*([fm])\b")


def text_key(value):
    """Chave de nome. ♀/♂ viram palavras antes do corte ASCII (antes, Nidoran♀ == Nidoran♂);
    o alias do catálogo 'Nidoran F'/'Nidoran M' é tratado explicitamente."""
    value = str(value or "")
    for symbol, word in _GENDER:
        value = value.replace(symbol, word)
    value = _NIDORAN_ALIAS.sub(lambda m: "nidoran " + ("female" if m.group(1) == "f" else "male"), value.lower())
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", value.lower())


def number_key(value):
    """Número sem zeros à esquerda; preserva prefixo/sufixo (TG01, 50a).

    Nenhum dos dois snapshots tem '/' nesses campos; se aparecer, o texto fica
    inteiro (sem casar) em vez de cortar um sufixo de coleção como denominador.
    """
    head = str(value or "").strip().upper()
    match = re.fullmatch(r"([A-Z-]*)0*(\d+)([A-Z]*)", head)
    if match:
        return f"{match.group(1)}{int(match.group(2))}{match.group(3)}"
    return head


def build_bridge(references, catalog):
    """references: dicts com ID EN/Carta/Código EN/Set EN; catalog: linhas do Catálogo EN."""
    index = defaultdict(list)
    for row in catalog:
        index[(text_key(row["Set"]), number_key(row["Número"]), text_key(row["Nome (PokeData)"]))].append(row)
    bridge = []
    for ref in references:
        hits = index.get((text_key(ref["Set EN"]), number_key(ref["Código EN"]),
                          text_key(ref["Carta inglesa — referência"])), [])
        ids = sorted({h["ID PokeData"] for h in hits})
        status = "sem_match" if not ids else ("unico" if len(ids) == 1 else "ambiguo")
        bridge.append({
            "id_en_parcial": ref["ID EN"], "carta_parcial": ref["Carta inglesa — referência"],
            "codigo_parcial": ref["Código EN"], "set_parcial": ref["Set EN"],
            "metodo": "set+numero+nome_pokedata", "status": status,
            "ids_pokedata": ";".join(str(i) for i in ids),
            "numeros_impressos_catalogo": ";".join(sorted({str(h["Número impresso"]) for h in hits})),
            "nomes_catalogo": ";".join(sorted({str(h["Nome (PokeData)"]) for h in hits})),
        })
    return bridge


def id_namespace_check(references, catalog):
    """Quantos inteiros coincidem e quantos desses apontam para a mesma carta."""
    by_id = {row["ID PokeData"]: row for row in catalog}
    overlap = [ref for ref in references if ref["ID EN"] in by_id]
    same = [ref for ref in overlap
            if text_key(by_id[ref["ID EN"]]["Set"]) == text_key(ref["Set EN"])
            and number_key(by_id[ref["ID EN"]]["Número"]) == number_key(ref["Código EN"])]
    return {"numeric_overlap": len(overlap), "overlap_same_set_and_number": len(same)}


def _records(workbook, sheet, header_row):
    rows = workbook[sheet].iter_rows(min_row=header_row, values_only=True)
    header = next(rows)
    return [dict(zip(header, row)) for row in rows if any(v is not None for v in row)]


def load_inputs():
    from openpyxl import load_workbook
    with zipfile.ZipFile(ROOT / "inputs/pokedata_crossref.zip") as archive:
        data = archive.read(CATALOG_MEMBER)
    w = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    catalog = _records(w, "Catálogo EN", 1)
    w.close()
    w = load_workbook(PARTIAL, read_only=True, data_only=True)
    references = _records(w, "Cobertura EN", 4)
    w.close()
    return references, catalog


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", help="CSV de saída (gitignored); omitido = só resumo")
    args = parser.parse_args(argv)
    references, catalog = load_inputs()
    bridge = build_bridge(references, catalog)
    if args.output:
        with open(args.output, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(bridge)
    summary = dict(Counter(row["status"] for row in bridge))
    print({"references": len(bridge), "status": summary,
           "id_namespace": id_namespace_check(references, catalog)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
