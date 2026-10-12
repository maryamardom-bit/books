"""
WooCommerce amount -> Toman conversion for imported historical data.

Every Django money field (Order.total_price, OrderItem.price, Payment.amount, wallet_balance) is
in Toman. WooCommerce stores each order amount in the store currency that was active when the
order was placed (`_order_currency`), so conversion must be driven by that code, never by the
size of the number.

The factors below are the Persian WooCommerce currency codes as identified in the P0-2 audit.
They are provisional: the original store's currency settings have not been independently
verified, in particular that IRHT means "thousand Toman" for this store.
"""

import math
import re
from decimal import ROUND_HALF_UP, Decimal, localcontext

TOMAN_PER_UNIT = {
    'IRR': Decimal('0.1'),    # Rial
    'IRT': Decimal('1'),      # Toman
    'IRHR': Decimal('100'),   # thousand Rial
    'IRHT': Decimal('1000'),  # thousand Toman
}

_DECIMAL_STRING = re.compile(r'[+-]?[0-9]+(\.[0-9]+)?', re.ASCII)


class MoneyConversionError(ValueError):
    pass


class InvalidAmountError(MoneyConversionError):
    pass


class UnsupportedCurrencyError(MoneyConversionError):
    pass


def parse_amount(raw):
    """Return a finite, non-negative Decimal; reject anything that is not an exact decimal amount."""
    if isinstance(raw, bool):
        raise InvalidAmountError(f'Amount must be numeric, got {raw!r}')
    if isinstance(raw, Decimal):
        amount = raw
    elif isinstance(raw, int):
        amount = Decimal(raw)
    elif isinstance(raw, float):
        if not math.isfinite(raw):
            raise InvalidAmountError(f'Amount is not finite: {raw!r}')
        # repr() gives the shortest decimal string that round-trips, avoiding binary artefacts.
        amount = Decimal(repr(raw))
    elif isinstance(raw, str):
        text = raw.strip()
        if not _DECIMAL_STRING.fullmatch(text):
            raise InvalidAmountError(f'Malformed amount: {raw!r}')
        amount = Decimal(text)
    else:
        raise InvalidAmountError(f'Unsupported amount type: {type(raw).__name__}')
    if not amount.is_finite():
        raise InvalidAmountError(f'Amount is not finite: {raw!r}')
    if amount < 0:
        raise InvalidAmountError(f'Amount is negative: {raw!r}')
    return amount


def normalize_currency(currency):
    if not isinstance(currency, str):
        raise UnsupportedCurrencyError(f'Currency code must be a string, got {currency!r}')
    code = currency.strip().upper()
    if code not in TOMAN_PER_UNIT:
        raise UnsupportedCurrencyError(f'Unsupported currency code: {currency!r}')
    return code


def woo_amount_to_toman(raw, currency):
    """Convert a WooCommerce amount in `currency` to whole Toman (ROUND_HALF_UP)."""
    amount = parse_amount(raw)
    factor = TOMAN_PER_UNIT[normalize_currency(currency)]
    sign, digits, exponent = amount.as_tuple()
    with localcontext() as ctx:
        # Enough precision that neither the multiplication nor the quantize can round silently.
        ctx.prec = max(28, len(digits) + abs(exponent) + 10)
        return int((amount * factor).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
