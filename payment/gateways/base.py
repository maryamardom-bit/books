from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from django.conf import settings


class GatewayError(Exception):
    """Transport failure: the gateway state is unknown, so nothing may be marked failed or paid."""


class PaymentRejected(Exception):
    """The gateway answered and refused the request."""


@dataclass
class GatewayRedirect:
    url: str
    token: str


@dataclass
class CallbackData:
    reference: str
    success: bool
    transaction_id: str = ''
    raw: dict = field(default_factory=dict)


@dataclass
class VerifyResult:
    success: bool
    amount: int = 0
    transaction_id: str = ''
    rrn: str = ''
    trace_no: str = ''
    card_mask: str = ''
    message: str = ''
    raw: dict = field(default_factory=dict)


class PaymentGateway(ABC):
    """
    Contract every gateway (SEP, ZarinPal, IDPay, ...) implements.
    The browser callback is never trusted on its own: only verify() can mark a payment paid.
    """

    name = ''

    def to_gateway_amount(self, amount):
        """Store amounts are Toman; Iranian gateways expect Rial."""
        return int(amount) * settings.PAYMENT_AMOUNT_MULTIPLIER

    @abstractmethod
    def request_payment(self, payment, callback_url):
        """Return a GatewayRedirect. Raise GatewayError or PaymentRejected."""

    @abstractmethod
    def parse_callback(self, data):
        """Turn the raw callback QueryDict into CallbackData."""

    @abstractmethod
    def verify(self, payment, callback):
        """Server-to-server verification. Return VerifyResult or raise GatewayError."""

    def reverse(self, payment):
        """Refund a verified transaction (best effort). Return True on success."""
        return False
