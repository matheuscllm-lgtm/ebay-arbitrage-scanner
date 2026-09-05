"""Report every decision and the exact sales behind each calculation."""
import json
from .report import escape_md, md_url


def render(payload):
    def num(value):
        return 'pendente' if value is None else f'{value:.2f}'
    rows = payload.get('rows', [])
    lines = ['# EBAY PSA — avaliação de cartas certificadas', '',
             'APROVAR é aprovação na análise; nenhuma compra é executada.', '',
             '| Carta / coleção / idioma / nota | Compra US$ | Investimento US$ | PSA original US$ | Comparação US$ | Revenda US$ | Lucro US$ | Desconto % | Margem líquida % | ROI líquido % | Decisão |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        s=r['strategy']
        label=escape_md(f'{r["card"]} #{r["number"]} / {r["set"]} / {r["language"]} / {r["grade"]}')
        values=[num(r['price']) if s['purchase_currency']=='USD' else 'pendente',num(s['investment_total']),num(s['psa_reference_original']),
                num(s['comparison_reference']),num(s['resale_estimate']),num(s['profit_estimate']),
                num(r['discount_pct']) if s['comparison_reference'] is not None else 'pendente',
                num(s['net_margin_percent']),num(s['net_roi_percent']),r['verdict']]
        lines.append('| '+f'[{label}]({md_url(r["url"])})'+' | '+' | '.join(values)+' |')
    for r in rows:
        s=r['strategy']
        lines += ['', f'## {escape_md(r["card"])} #{escape_md(r["number"])} — {r["verdict"]}', '',
                  'Motivos: '+escape_md('; '.join(r['reasons']) or 'regras e evidências atendidas')+'.',
                  'Variante: '+escape_md(', '.join(s['variant']) or 'sem modificadores identificados')+'.',
                  'Rota: COMC; compra no vault preferencial quando confirmada. Listagem direta no vault: não.',
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
                  'Teto BGS: '+num(s['comparison_cap'])+'.']
        for kind in ('psa','resale'):
            evidence=s.get(kind+'_evidence',{})
            label='Referência PSA' if kind=='psa' else 'Estimativa de revenda'
            lines += ['', f'{label}: {evidence.get("n_sales",0)} vendas; {evidence.get("n_used",0)} usadas na mediana; janela {evidence.get("window_days","—")} dias; dispersão {num(evidence.get("dispersion_percent"))}%.', '']
            for sale in s[kind+'_sales']:
                lines.append(f'- {sale["date"]} · US$ {num(sale["price"])} · [{escape_md(sale["title"])}]({md_url(sale["url"])})')
    if payload.get('meta',{}).get('aborted'):
        lines += ['', 'EXECUÇÃO ABORTADA: resultado parcial; não representa busca completa.']
    lines += ['', 'Desconto = (comparação − compra)/comparação. Margem líquida = lucro/venda bruta. ROI líquido = lucro/investimento. Valores pendentes nunca são zero.', '']
    return '\n'.join(lines)
