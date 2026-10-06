"""Pure, conservative identity rules shared by offline research stages.

These helpers never prove printing/finish equivalence or economic value.
"""

def art_eligible(evidence):
    """An image-rule candidate needs sufficient points AND compatible names."""
    return evidence[1] >= 1 and evidence[0].get('n_in', 0) >= 40


def add_bridge_candidates(conf, reverse, probable, gray, measured):
    """A JP bridge is a candidate only; never override a direct assessment."""
    for en, japanese in conf['EN_JA'].items():
        for jp in japanese:
            for cn in reverse['CH_JA'].get(jp, {}):
                if (en, cn) in measured:
                    continue
                if any(cn in mapping.get(en, {}) for mapping in
                       (conf['EN_CH'], probable['EN_CH'], gray['EN_CH'])):
                    continue
                probable['EN_CH'].setdefault(en, {})[cn] = (
                    {'via_jp': jp}, 0, 'via',
                    'candidata via japonês; comparação direta EN-CHS e versão pendentes')


def overall_status(values):
    """Catalog absence and empty third-party lists cannot prove exclusivity."""
    if 'arte confirmada' in values:
        return 'arte confirmada'
    if any(v.startswith('provável') for v in values):
        return 'provável'
    if all(v == 'não encontrada' for v in values):
        return 'não encontrada'
    return 'inconclusivo'
