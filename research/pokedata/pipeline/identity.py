"""Regras puras de identidade e exclusividade (revisão Claude, issue #56).

Sem I/O: `build_xlsx.py` usa estas funções, e `research/pokedata/test_identity.py`
as testa com fixtures. Nada aqui confirma arte ou impressão; só evita perder
impressões distintas na deduplicação e declarar exclusividade sem evidência.
"""
import re

_NUM = re.compile(r'([A-Za-z-]*)0*(\d+)([A-Za-z]*)')


def number_identity(num):
    """Número de coleção sem zeros à esquerda, preservando prefixo e sufixo.

    '036' == '36'; 'GG01' != '001'; 'H3' != '3'; '50a' != '50b'. O campo `num`
    do catálogo não traz denominador; se trouxer, ele é mantido (não é cortado).
    """
    s = str(num or '').strip()
    m = _NUM.fullmatch(s)
    if not m:
        return s.upper()
    return f"{m.group(1).upper()}{int(m.group(2))}{m.group(3).upper()}"


def unit_identity(k):
    """Chave de unidade (set_id, número, nome) com o número normalizado.

    O set_id já carrega idioma e edição do catálogo. O nome entra para que
    'Glaceon ex' e 'Glaceon ex Holiday Calendar' não se apaguem.
    """
    return (k[0], number_identity(k[1]), k[2])


def correspondence_signature(k, first_jp, first_cn):
    """Assinatura de deduplicação da aba Correspondência (antes: primeiro inteiro do número)."""
    return unit_identity(k) + (first_jp, first_cn)


def dedupe_ranked(keys):
    """Remove só cadastros duplos da mesma carta ('036' e '36' com o mesmo nome)."""
    out, seen = [], set()
    for k in keys:
        sig = unit_identity(k)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(k)
    return out


JP_NOT_FOUND = 'inconclusivo: sem impressão internacional encontrada nas fontes consultadas'
JP_UNCHECKED = 'inconclusivo: sem evidência positiva de exclusividade (Limitless não consultado ou sem desfecho)'
JP_INTL = 'inconclusivo: Limitless lista impressão internacional fora do PokeData'


def reclassify_jp_exclusive(status, checked, intl_prints):
    """Ausência no Limitless não comprova exclusividade JP.

    status: dict do assemble para uma unidade JP com geral == 'exclusiva'.
    checked: True se `lim_jp` achou a página da mesma carta; intl_prints: lista do pickle.
    Retorna um novo dict; nunca altera o original (o rótulo herdado fica rastreável).
    """
    if status.get('geral') != 'exclusiva':
        return dict(status)
    new = dict(status)
    new['geral'] = 'inconclusivo'
    new['ENGLISH'] = (JP_INTL if intl_prints else JP_NOT_FOUND) if checked else JP_UNCHECKED
    new['herdado'] = 'exclusiva'
    return new
