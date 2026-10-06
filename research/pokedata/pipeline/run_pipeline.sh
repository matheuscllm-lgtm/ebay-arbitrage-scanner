#!/usr/bin/env bash
# Ordem completa do processo. Rodar de dentro de uma pasta de trabalho vazia:
#   mkdir trabalho && cd trabalho && bash ../run_pipeline.sh
# As etapas de download pulam o que já foi baixado; as de cálculo refazem o arquivo de saída.
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-PokeData_catalogo_correspondencia.xlsx}"
PR53="${2:-}"   # opcional: caminho da planilha do PR #53

python3 "$R/preflight.py" ${PR53:+"$PR53"}         # 0  checagem offline (dependências, disco, pasta não versionada, coleta)
python3 "$R/fetch_cards.py"                       # 1  sets e cartas do PokeData
python3 "$R/fetch_external.py"                    # 2  pokemon-tcg-data, TCGdex (sets), PokeAPI
python3 "$R/fetch_tcgdex.py"                      # 2b TCGdex (cartas)
python3 "$R/catalog.py"                           # 3  catálogo
python3 "$R/dl_images.py"                         # 4  imagens
python3 "$R/extract.py" 0 2 &                     # 5  descritores, uma parte por núcleo
extract_pid_0=$!
python3 "$R/extract.py" 1 2 &
extract_pid_1=$!
# Bare `wait` returns success even if one of the children failed.
# Reap both children, then stop before consuming incomplete descriptors.
extract_status=0
wait "$extract_pid_0" || extract_status=1
wait "$extract_pid_1" || extract_status=1
if (( extract_status != 0 )); then
  echo "Falha na extração de descritores; processamento interrompido." >&2
  exit "$extract_status"
fi
python3 "$R/detect_placeholders.py"               # 6  imagens-marcador

for par in "ENGLISH JAPANESE" "ENGLISH CHINESE" "CHINESE JAPANESE"; do
  python3 "$R/match.py" $par                      # 7  candidatas e primeira comparação
done
for tag in EN_JA EN_CH CH_JA; do
  python3 "$R/stage2_run.py" "$tag"               # 8  segunda comparação
done

python3 "$R/limitless_todo.py"                    # 9a cartas em inglês sem par
python3 "$R/fetch_limitless.py"                   # 9b consulta ao Limitless
python3 "$R/limitless_pairs.py"                   # 9c pares indicados
python3 "$R/stage2_pairs.py" lim_pairs.pkl s2_LIM.pkl   # 9d comparação de imagem
python3 "$R/limitless_classify.py"                # 9e resultado

python3 "$R/assemble.py"                          # 10 classificação
python3 "$R/lim_jp.py"                            # 11 evidência externa das exclusivas japonesas (Limitless)
python3 "$R/assemble.py"                          # 11b aplica essa evidência
python3 "$R/build_xlsx.py" "$OUT" ${PR53:+"$PR53"}   # 12 planilha; PR53=<planilha do PR #53> acrescenta cobertura e chinês tradicional
echo "Planilha gerada: $OUT (recalcular as fórmulas no Excel ou LibreOffice)"

