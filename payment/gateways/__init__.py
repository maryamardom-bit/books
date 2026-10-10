from django.conf import settings

from .base import (  # noqa: F401
    CallbackData,
    GatewayError,
    GatewayRedirect,
    PaymentGateway,
    PaymentRejected,
    VerifyResult,
)
from .sep import SepGateway

# TODO(Phase 2 - Payment): ZarinPalGateway / IDPayGateway implement the same PaymentGateway contract.
GATEWAYS = {
    SepGateway.name: SepGateway,
}


def get_gateway(name=None):
    return GATEWAYS[name or settings.PAYMENT_GATEWAY]()
