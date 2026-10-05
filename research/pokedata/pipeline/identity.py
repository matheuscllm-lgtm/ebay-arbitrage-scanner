"""Regras de identidade e classificação, sem dependência de dados baixados.

Correções da revisão conjunta do PR #53 (C1, C2, C4 em docs/POKEDATA_REVIEW.md):
- C2: a chave de impressão usa o número completo (prefixo + dígitos + sufixo) e o
  nome base. Antes, só os dígitos finais: GG01 colidia com 001, H3 com 3.
- C1: "exclusiva" exige evidência positiva de ausência em TODOS os idiomas-alvo,
  inclusive chinês tradicional. Ausência no catálogo não é evidência.
- C4: a comparação por imagem confirma a arte; a impressão (edição, acabamento,
  carimbo) não é conferida pelo pipeline e fica pendente.
"""
import re

# idiomas-alvo de uma carta de um idioma de origem; CHT está no escopo do projeto
TARGETS = {
    'ENGLISH': ('JAPANESE', 'CHINESE', 'CHINESE_T'),
    'JAPANESE': ('ENGLISH', 'CHINESE', 'CHINESE_T'),
    'CHINESE': ('ENGLISH', 'JAPANESE', 'CHINESE_T'),
}
LABEL = {'ENGLISH': 'EN', 'JAPANESE': 'JP', 'CHINESE': 'CHS', 'CHINESE_T': 'CHT'}
CANDIDATE = 'candidata a exclusiva'


def number_key(value):
    """Número antes do denominador, sem zeros à esquerda; preserva prefixo/sufixo.

    Mesmo formato de bridge_partial_ids.number_key: '001'→'1', 'GG01'→'GG1',
    '50a'→'50A', 'H3'→'H3', '121/106'→'121'.
    """
    head = str(value or '').split('/')[0].strip().upper()
    match = re.fullmatch(r'([A-Z-]*)0*(\d+)([A-Z]*)', head)
    if match:
        return f'{match.group(1)}{int(match.group(2))}{match.group(3)}'
    return head


def print_key(unit):
    """Chave de deduplicação de uma carta única (set_id, número, nome-chave).

    Junta só o cadastro duplo do mesmo nome ('036' e '36'); impressões com número
    ou nome distintos no mesmo set ('GG01'×'001', '50a'×'50b') ficam separadas.
    """
    set_id, num, name_key = unit
    return (set_id, number_key(num), name_key)


def single_language(lang, statuses, evidence=None):
    """Situação geral de uma carta sem equivalente confirmado.

    statuses: situação por idioma-alvo calculada pelo pipeline (`assemble.py`).
    evidence: {idioma: 'ausente' | lista de impressões encontradas} vinda de fonte
    externa com cobertura do idioma (ex.: Limitless para EN). Idioma sem entrada
    não foi pesquisado.
    Retorna (geral, motivo). 'exclusiva' só com ausência comprovada em todos os
    idiomas-alvo; caso contrário, 'inconclusivo' com o motivo explícito.
    """
    evidence = evidence or {}
    if any(v == 'confirmado' for v in statuses.values()):
        return 'confirmado', ''
    found = {t: v for t, v in evidence.items() if isinstance(v, (list, tuple)) and v}
    if found:
        t, prints = next(iter(found.items()))
        return 'inconclusivo', (f'{LABEL[t]} existe segundo fonte externa ({"; ".join(prints[:3])}); '
                                'arte não confirmada')
    absent_here = all(v == 'não encontrado' or v.startswith('exclusiva') for v in statuses.values())
    if not absent_here:
        return 'inconclusivo', ''
    parts = []
    for t in TARGETS[lang]:
        if evidence.get(t) == 'ausente':
            parts.append(f'{LABEL[t]}: ausência confirmada por fonte externa')
        elif t in statuses:
            parts.append(f'{LABEL[t]}: não encontrada no catálogo (ausência não comprova)')
        else:
            parts.append(f'{LABEL[t]}: não pesquisado')
    if all(evidence.get(t) == 'ausente' for t in TARGETS[lang]):
        return 'exclusiva', '; '.join(parts)
    return 'inconclusivo', f'{CANDIDATE}: ' + '; '.join(parts)


def match_level(points):
    """C4: nível da correspondência a partir dos pontos coincidentes de cada idioma.

    A arte é 'confirmada' com 40+ pontos em todos os pares, 'provável' entre 12 e 39.
    A impressão nunca é conferida aqui.
    """
    pts = [p for p in points if p not in ('', None)]
    arte = 'confirmada' if (not pts or min(pts) >= 40) else 'provável'
    return arte, 'não conferida'
