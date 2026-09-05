"""Per-card storage forecast in USD. Published rates; explicit holding horizon."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal


def estimate_storage(costs, resale, today=None):
    """Storage bill dates after the 90-day grace, plus daily enhanced security.

    resale is the seller's expected asking price. COMC's buyer shipping markup
    is only used for the security fee's list-price base; it is not seller revenue
    or an additional acquisition shipping charge. This is an estimate, not a bill.
    """
    today = today or datetime.now(timezone.utc).date()
    horizon = costs.get('storage_horizon_days')
    if horizon is None or resale is None:
        return None, {'status': 'prazo-ou-preco-de-revenda-pendente'}
    end = today + timedelta(days=horizon)
    grace_end = today + timedelta(days=costs['storage_free_days'])
    month = date(today.year, today.month, 1)
    billed = []
    while month <= end:
        if month >= grace_end and month > today:
            billed.append(month.isoformat())
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    storage = Decimal(str(costs['storage_monthly_usd'])) * len(billed) if resale > Decimal('0.75') else Decimal(0)
    list_price = resale + Decimal(str(costs['buyer_shipping_markup_usd']))
    security = (list_price * Decimal(str(costs['security_daily_fraction'])) * horizon
                if list_price > Decimal(str(costs['security_threshold_usd'])) else Decimal(0))
    return storage + security, {'status': 'estimado', 'start_date': today.isoformat(),
                               'horizon_days': horizon, 'end_date': end.isoformat(),
                               'storage_billing_dates': billed, 'storage_exact': str(storage),
                               'security_exact': str(security), 'security_list_price_exact': str(list_price)}
