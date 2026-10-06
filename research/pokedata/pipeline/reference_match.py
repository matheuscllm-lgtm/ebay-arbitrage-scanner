"""Resolução de referências e normalização de códigos — regras puras, sem I/O.

Revisão Claude (issue #56, 06/10/2026), pendência 2 de docs/POKEDATA_FIXES_20261005.md.
Usado por `build_xlsx.py` (aba Cobertura PR53), `compare_pr53.py` e pela ponte
`../bridge_partial_ids.py`. Nada aqui confirma arte, versão ou impressão: as regras só
impedem que um candidato seja escolhido em silêncio quando há mais de um, e que
grafias diferentes do mesmo código pareçam códigos diferentes (ou o contrário).
"""
import re

from common import key, split_name

_NUM = re.compile(r'([A-Z-]*)0*(\d+)([A-Z]*)')
_PROMO_SET = re.compile(r'[A-Za-z]+-P')


def number_norm(value):
    """Número de coleção comparável: tira zeros à esquerda e preserva prefixo e sufixo.

    '036' → '36'; 'TG01' → 'TG1'; 'H05' → 'H5' (nunca '5'); '50a' → '50A'.
    Texto sem o formato prefixo+dígitos+sufixo fica inteiro, em maiúsculas: um
    denominador ('121/106') nunca é cortado aqui; isso só acontece em `local_code`.
    """
    s = str(value if value is not None else '').strip().upper()
    m = _NUM.fullmatch(s)
    return f'{m.group(1)}{int(m.group(2))}{m.group(3)}' if m else s


def set_norm(code):
    """Código de set comparável: maiúsculas, '+' → 'P' (SM4+ = SM4p), só letras e dígitos.

    'PROMOSV…' sem denominador vira 'SVP', o set promocional (ver `local_code`).
    Subprodutos ('151C4') NÃO viram o set-pai ('151C'): ver `same_print`.
    """
    s = re.sub(r'[^A-Z0-9]', '', str(code or '').strip().upper().replace('+', 'P'))
    return 'SVP' if s.startswith('PROMOSV') else s


def local_code(code):
    """Código local da base parcial → (set, número) comparável, ou None se ilegível.

    'M4 114/083' → ('M4', '114');  'SM4+ 120/114' → ('SM4P', '120');
    'PROMOSV08 092/SV-P' → ('SVP', '92'): o set promocional vem do denominador;
    'CBB5C 08 07/07' → ('CBB5C', '807'): pacote de gemas, o catálogo grafa '0807';
    'SV2a F 170/165' → ('SV2AF', '170'): letra solta faz parte do código do set.
    """
    parts = str(code or '').split()
    if len(parts) < 2:
        return None
    set_code, rest = parts[0], parts[1:]
    if len(rest) == 2 and rest[0].isalpha():
        set_code, rest = set_code + rest[0], rest[1:]
    if len(rest) == 2 and rest[0].isdigit():
        rest = [rest[0] + rest[1]]
    if len(rest) != 1:
        return None
    head, _, denominator = rest[0].partition('/')
    if _PROMO_SET.fullmatch(denominator.strip()):
        set_code = denominator.strip()
    return set_norm(set_code), number_norm(head)


def same_print(local, codes):
    """Compara um código local com os códigos do catálogo: 'igual', 'subproduto' ou None.

    'subproduto': mesmo número e o set do catálogo é o código local sem a numeração
    final de subproduto (local '151C4' × catálogo '151C'). Não é 'igual': o catálogo
    não distingue o subproduto, então a impressão fica pendente. Exige que o set do
    catálogo termine em letra, para 'SV11W' × 'SV1' não passar por subproduto.
    """
    if local is None:
        return None
    if local in codes:
        return 'igual'
    set_code, number = local
    for cat_set, cat_number in codes:
        if (cat_number == number and cat_set and cat_set[-1].isalpha()
                and re.fullmatch(re.escape(cat_set) + r'\d+', set_code)):
            return 'subproduto'
    return None


def resolve_reference(ref_name, ref_number, candidates):
    """Escolhe o registro do catálogo de uma referência EN, sem desempatar no escuro.

    candidates: registros do mesmo set e do mesmo `number_norm`, como dicts com
    'id', 'nome' (nome completo no catálogo), 'unidade' (set_id, número, nome-chave)
    e 'numero' (grafia no catálogo). Retorna (unidade, registro, situação):

    - 'registro exato': um único registro com o mesmo nome completo;
    - 'registro exato (número literal)': nome igual em cadastro duplo do catálogo
      ('4' e '004'), desempatado pela grafia exata do número da referência;
    - 'mesma carta, registro aproximado': nenhum nome completo igual e uma única
      carta com o mesmo nome-base (registro None: a variante não foi conferida);
    - 'ambíguo: …': mais de um candidato possível; nada é escolhido;
    - 'não localizado: …': nome contido ou diferente não basta para localizar.
    """
    candidates = list(candidates)
    full = key(str(ref_name))
    exact = list({c['id']: c for c in candidates if key(str(c['nome'])) == full}.values())
    if len(exact) == 1:
        return exact[0]['unidade'], exact[0], 'registro exato'
    if exact:
        literal = [c for c in exact
                   if str(c['numero']).strip().upper() == str(ref_number).strip().upper()]
        if len(literal) == 1:
            return literal[0]['unidade'], literal[0], 'registro exato (número literal)'
        return None, None, f'ambíguo: {len(exact)} registros com o mesmo nome'
    base = key(split_name(str(ref_name))[0])
    units = sorted({c['unidade'] for c in candidates if c['unidade'][2] == base}, key=str)
    if len(units) == 1:
        return units[0], None, 'mesma carta, registro aproximado'
    if units:
        return None, None, f'ambíguo: {len(units)} cartas com o mesmo nome-base'
    if candidates:
        names = sorted({str(c['nome']) for c in candidates})
        return None, None, 'não localizado: mesmo set e número, nome diferente (' + '; '.join(names[:3]) + ')'
    return None, None, 'não localizado'
