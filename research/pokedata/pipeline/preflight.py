"""Etapa 0 — checagem offline antes de reprocessar. Uso: python preflight.py [planilha do PR #53]

Roda na pasta de trabalho, sem rede e sem gravar nada. Falha (código 1) quando o
reprocessamento não deve começar: dependência ausente, pouco disco, pasta de trabalho
versionada num repositório (os derivados não podem ser publicados: ver .gitignore),
coleta anterior marcada como incompleta ou planilha do PR #53 inexistente.
Intermediários antigos sem manifesto só geram aviso: o pipeline retoma downloads, mas
eles não comprovam completude nem atualidade (docs/POKEDATA_FIXES_20261005.md).
Roteiro completo: docs/POKEDATA_REPROCESSAMENTO.md.
"""
import argparse
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

MODULES = ('requests', 'numpy', 'cv2', 'PIL', 'openpyxl')  # requirements.txt desta pasta
TOOLS = ('curl',)                                           # fetch_cards.py
MIN_FREE_GB = 8                                             # ~7 GB de imagens e descritores
INTERMEDIATES = ('all_cards.json', 'catalog.pkl', 'result.pkl', 'lim_jp.pkl', 'unit_rep.json')


def check_python(version):
    ok = tuple(version[:2]) >= (3, 10)
    return ('OK' if ok else 'FALHA', f"Python {'.'.join(map(str, version[:3]))} (mínimo 3.10)")


def check_modules(missing):
    if missing:
        return 'FALHA', 'pacotes ausentes: ' + ', '.join(missing) + ' (pip install -r requirements.txt)'
    return 'OK', 'pacotes do requirements.txt importáveis'


def check_tools(missing):
    return ('FALHA', 'ferramentas ausentes: ' + ', '.join(missing)) if missing else ('OK', 'curl disponível')


def check_disk(free_bytes, min_gb=MIN_FREE_GB):
    gb = free_bytes / 1024 ** 3
    return ('OK' if gb >= min_gb else 'FALHA', f'{gb:.1f} GB livres (mínimo {min_gb} GB)')


def check_workdir(in_repo, ignored):
    """Pasta dentro de um repositório só serve se o Git a ignora (ex.: pipeline/trabalho/)."""
    if not in_repo:
        return 'OK', 'pasta de trabalho fora de repositório Git'
    if ignored:
        return 'OK', 'pasta de trabalho ignorada pelo Git'
    return 'FALHA', 'pasta de trabalho versionável: derivados poderiam ser publicados; use pipeline/trabalho/ ou uma pasta fora do repositório'


def check_collection(manifest, intermediates):
    """manifest: conteúdo de collection_manifest.json (None se ausente)."""
    if manifest is not None and manifest.get('complete') is not True:
        return 'FALHA', 'coleta anterior incompleta (collection_manifest.json); recomece a coleta'
    if manifest is None and intermediates:
        return 'AVISO', ('intermediários sem manifesto (' + ', '.join(intermediates) +
                         '): não comprovam completude nem atualidade; prefira pasta vazia')
    return 'OK', 'pasta vazia ou coleta anterior completa'


def check_pr53(path):
    if not path:
        return 'AVISO', 'sem planilha do PR #53: abas Cobertura PR53 e CHT PR53 não serão geradas'
    return ('OK', f'planilha do PR #53: {path}') if Path(path).is_file() else ('FALHA', f'planilha do PR #53 não encontrada: {path}')


def _git(*args, cwd):
    try:
        return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True).returncode == 0
    except OSError:
        return False


def run(workdir, pr53=None, min_free_gb=MIN_FREE_GB):
    missing = []
    for name in MODULES:
        try:
            importlib.import_module(name)
        except Exception:
            missing.append(name)
    manifest_path = workdir / 'collection_manifest.json'
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    except (OSError, ValueError):
        manifest = {'complete': None}  # manifesto ilegível conta como coleta incompleta
    in_repo = _git('rev-parse', '--is-inside-work-tree', cwd=workdir)
    ignored = in_repo and _git('check-ignore', '-q', str(workdir / '.preflight-probe'), cwd=workdir)
    return [
        check_python(sys.version_info),
        check_modules(missing),
        check_tools([t for t in TOOLS if shutil.which(t) is None]),
        check_disk(shutil.disk_usage(workdir).free, min_free_gb),
        check_workdir(in_repo, ignored),
        check_collection(manifest, [f for f in INTERMEDIATES if (workdir / f).exists()]),
        check_pr53(pr53),
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('pr53', nargs='?', default='', help='planilha do PR #53 (opcional)')
    parser.add_argument('--min-free-gb', type=float, default=MIN_FREE_GB)
    args = parser.parse_args(argv)
    results = run(Path.cwd(), args.pr53, args.min_free_gb)
    for status, message in results:
        print(f'[{status}] {message}')
    if any(status == 'FALHA' for status, _ in results):
        print('Pré-checagem falhou; reprocessamento não iniciado.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
