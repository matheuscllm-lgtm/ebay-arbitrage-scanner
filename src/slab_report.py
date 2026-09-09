"""Report every decision and the exact sales behind each calculation."""

from .chat_format import reference_price
from .report import links_cell, policy_funnel_lines
import json
from collections import Counter
from .report import escape_md, md_url


def _nd(value):
    """Valor de `meta` para exibição: ausente = 'n/d' (nunca inventado); número sem zeros à toa."""
    if value is None or value == '':
        return 'n/d'
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return f'{value:g}'
    return str(value)


def collection_line(meta):
    """QUANDO, O QUE e COM QUAL REGRA a coleta rodou — tudo lido de `meta` do JSON do scan
    (DELIVERY_CHAT.md: horário da coleta e regra identificados na entrega). Nada é
    recalculado aqui; campo ausente sai como n/d (auditoria de honestidade 2026-09-09)."""
    meta = meta or {}
    cfg = meta.get('config') or {}
    policy = cfg.get('slab_strategy') or {}
    economics = policy.get('economics') or {}
    funnel = meta.get('funnel') or {}
    stamp = str(meta.get('timestamp') or '')
    if stamp:
        when = stamp[:16].replace('T', ' ') + (' UTC' if stamp.endswith(('+00:00', 'Z')) else ' ' + stamp[19:])
    else:
        when = 'n/d'
    group = f"grupo `{meta['group']}`" if meta.get('group') else 'grupo n/d'
    return ' · '.join([
        when, group, f"{_nd(meta.get('watchlist_count'))} carta(s) da watchlist",
        f"política `{_nd(policy.get('version'))}` (`gate_mode: {_nd(economics.get('gate_mode'))}` · "
        f"`min_profit_usd: {_nd(economics.get('min_profit_usd'))}` · "
        f"`min_discount_percent: {_nd(economics.get('min_discount_percent'))}`)",
        f"`min_price_usd: {_nd(cfg.get('min_price_usd'))}`", f"`max_pages: {_nd(cfg.get('max_pages'))}`",
        f"chamadas à Browse API: {_nd(funnel.get('ebay_calls'))} (`max_ebay_calls: {_nd(cfg.get('max_ebay_calls'))}`)",
    ])


def render(payload):
    def num(value):
        return 'pendente' if value is None else f'{value:.2f}'
    rows = payload.get('rows', [])
    counts = Counter(r['verdict'] for r in rows)
    meta = payload.get('meta') or {}
    lines = ['# EBAY PSA — avaliação de cartas certificadas', '',
             f'{len(rows)} candidatos: {counts["APROVAR"]} APROVAR, {counts["REVISAR"]} REVISAR, {counts["REJEITAR"]} REJEITAR.', '',
             'Coleta: ' + (escape_md(collection_line(meta)) if meta
                           else 'n/d (sem metadados do scan; ver a entrega canônica via ebay_summary.py)'), '',
             'APROVAR é aprovação na análise; nenhuma compra é executada.', '',
             '| Carta / coleção / idioma / nota | Compra US$ | Investimento US$ | PSA original US$ | Comparação US$ | Revenda US$ | Lucro US$ | Desconto % | Margem líquida % | ROI líquido % | Decisão | Links |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|']
    if meta.get('aborted'):
        # Causa da parcialidade (review #32): parada antecipada x erros contados no funil.
        cause = ('parada antecipada (autenticação, cota ou API): cartas restantes NÃO foram varridas'
                 if (meta.get('funnel') or {}).get('stopped_early')
                 else 'todas as cartas foram visitadas, mas houve erros contados no funil')
        lines[2:2] = [f'**EXECUÇÃO ABORTADA: resultado parcial; não representa busca completa — {cause}.**', '']
    for r in rows:
        s=r['strategy']
        label=escape_md(f'{r["card"]} #{r["number"]} / {r["set"]} / {s.get("listing_language") or "idioma não confirmado"} / {r["grade"]}')
        values=[num(r['price']) if s['purchase_currency']=='USD' else 'pendente',num(s['investment_total']),reference_price(num(s['psa_reference_original']), r.get('pc_url')),
                reference_price(num(s['comparison_reference']), r.get('pc_url')),reference_price(num(s['resale_estimate']), next((x.get('url') for x in s.get('resale_sales', []) if x.get('url')), None)),num(s['profit_estimate']),
                num(r['discount_pct']) if s['comparison_reference'] is not None else 'pendente',
                num(s['net_margin_percent']),num(s['net_roi_percent']),r['verdict'],links_cell(r.get('url'), r.get('pc_url'))]
        lines.append('| '+f'[{label}]({md_url(r["url"])})'+' | '+' | '.join(values)+' |')
    for r in rows:
        s=r['strategy']
        lines += ['', f'## {escape_md(r["card"])} #{escape_md(r["number"])} — {r["verdict"]}', '',
                  'Motivos: '+escape_md('; '.join(r['reasons']) or 'regras e evidências atendidas')+'.',
                  'Variante: '+escape_md(', '.join(s['variant']) or 'sem modificadores identificados')+'.',
                  'Idioma do alvo: '+escape_md(r['language'])+'; idioma identificado no anúncio: '+escape_md(s.get('listing_language') or 'não confirmado')+'.',
                  'Evidência do idioma: '+escape_md(s.get('language_source', 'titulo'))+'.',
                  'Anúncio: '+escape_md(r.get('title', ''))+'.',
                  f'[Oferta]({md_url(r["url"])}) · [Fonte das vendas]({md_url(r.get("pc_url", ""))})',
                  'Rota: COMC; compra no vault preferencial quando confirmada. Listagem direta no vault: não.',
                  'Vault: '+('confirmado' if s.get('vault_confirmed') is True else 'não está no vault' if s.get('vault_confirmed') is False else 'não confirmado')+'.',
                  'Categoria: '+escape_md(s['slab_category'])+'.',
                  'Custos: reserva de envio/taxas US$ '+num(s['costs']['reserve_usd'])+
                  '; processamento COMC US$ '+num(s['costs']['comc_processing_usd'])+
                  '; armazenamento US$ '+num(s['costs']['comc_storage_usd'])+
                  '; venda '+num(s['costs']['selling_fee_percent'])+
                  '%; saque '+num(s['costs']['cashout_fee_percent'])+'%.',
                  'Frete observado no anúncio: US$ '+num(s['costs']['listing_shipping_observed_usd'])+
                  ' (informativo, não somado novamente à reserva).',
                  'Subtotal conhecido (pode estar incompleto): US$ '+num(s['investment_known_subtotal'])+'.',
                  'Ajustes de comparação: '+escape_md(json.dumps(s['adjustments']))+'.',
                  'Teto de comparação da certificadora (preço do item): US$ '+num(s['comparison_cap'])+'.',
                  'Regra econômica aplicada: '+escape_md(json.dumps(s.get('economic_gate', {'status': 'pendente'}), ensure_ascii=False))+'.']
        if s['costs'].get('storage_forecast'):
            lines.append('Projeção de armazenamento e segurança: '+escape_md(json.dumps(s['costs']['storage_forecast'], ensure_ascii=False))+'.')
        for kind in ('psa','resale'):
            if kind == 'resale' and s['psa_sales'] and s['resale_sales'] == s['psa_sales']:
                lines += ['', 'Estimativa de revenda: usa a mesma amostra PSA detalhada acima.']
                continue
            evidence=s.get(kind+'_evidence',{})
            label='Referência PSA' if kind=='psa' else 'Estimativa de revenda'
            lines += ['', f'{label}: {evidence.get("n_sales",0)} vendas; {evidence.get("n_used",0)} usadas na mediana; janela {evidence.get("window_days","—")} dias; dispersão {num(evidence.get("dispersion_percent"))}%.', '']
            if evidence.get('excluded_counts'):
                lines.append('Vendas excluídas por motivo: '+escape_md(json.dumps(evidence['excluded_counts'], ensure_ascii=False))+'.')
            for sale in s[kind+'_sales']:
                lines.append(f'- {sale["date"]} · US$ {num(sale["price"])} · [{escape_md(sale["title"])}]({md_url(sale["url"])})')
    if meta.get('aborted'):
        lines += ['', 'EXECUÇÃO ABORTADA: resultado parcial; não representa busca completa.']
    # Funil com rotulos humanos (nada some: contador sem rotulo sai em "outros: ...").
    # Sem funil no meta = n/d: um dict vazio viraria "analisados: 0", zero inventado.
    funnel = meta.get('funnel')
    lines += ['', 'Funil da busca: ' + (escape_md(' · '.join(policy_funnel_lines(funnel))) if funnel is not None
                                       else 'n/d (sem metadados do scan; ver a entrega canônica via ebay_summary.py)') + '.']
    lines += ['', 'Desconto = (comparação − compra)/comparação. Margem líquida = lucro/venda bruta. ROI líquido = lucro/investimento. Valores pendentes nunca são zero.', '']
    return '\n'.join(lines)
