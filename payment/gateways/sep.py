"""Saman Electronic Payment (SEP) online gateway."""

import logging
from urllib.parse import quote

import requests
from django.conf import settings

from .base import CallbackData, GatewayError, GatewayRedirect, PaymentGateway, PaymentRejected, VerifyResult

logger = logging.getLogger(__name__)

# Callback fields worth keeping for support/audit. Card data arrives masked/hashed only.
_CALLBACK_FIELDS = (
    'State', 'Status', 'RefNum', 'ResNum', 'TerminalId', 'TraceNo', 'Rrn',
    'Amount', 'AffectiveAmount', 'Wage', 'SecurePan',
)
SUCCESS_STATUS = '2'
ALREADY_VERIFIED_CODE = 2


class SepGateway(PaymentGateway):
    name = 'sep'

    TOKEN_URL = 'https://sep.shaparak.ir/onlinepg/onlinepg'
    REDIRECT_URL = 'https://sep.shaparak.ir/OnlinePG/SendToken'
    VERIFY_URL = 'https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction'
    REVERSE_URL = 'https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/ReverseTransaction'

    def __init__(self, terminal_id=None, timeout=None):
        self.terminal_id = str(terminal_id or settings.SEP_TERMINAL_ID)
        self.timeout = timeout or settings.PAYMENT_HTTP_TIMEOUT

    def _terminal_number(self):
        return int(self.terminal_id) if self.terminal_id.isdigit() else self.terminal_id

    def _post(self, url, payload):
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            return response.status_code, response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning('SEP request to %s failed: %s', url, exc.__class__.__name__)
            raise GatewayError(str(exc)) from exc

    def request_payment(self, payment, callback_url):
        status_code, data = self._post(self.TOKEN_URL, {
            'action': 'token',
            'TerminalId': self.terminal_id,
            'Amount': self.to_gateway_amount(payment.amount),
            'ResNum': payment.reference.hex,
            'RedirectUrl': callback_url,
        })
        if not isinstance(data, dict):
            raise PaymentRejected('invalid response')
        token = data.get('token')
        if status_code != 200 or str(data.get('status')) != '1' or not token:
            raise PaymentRejected(str(data.get('errorDesc') or data.get('errorCode') or 'token rejected'))
        return GatewayRedirect(url=f'{self.REDIRECT_URL}?token={quote(token)}', token=token)

    def parse_callback(self, data):
        return CallbackData(
            reference=(data.get('ResNum') or '').strip(),
            success=str(data.get('Status') or '').strip() == SUCCESS_STATUS,
            transaction_id=(data.get('RefNum') or '').strip(),
            raw={key: data.get(key) for key in _CALLBACK_FIELDS if data.get(key) is not None},
        )

    def verify(self, payment, callback):
        if not callback.transaction_id:
            return VerifyResult(success=False, message='missing RefNum')
        _, data = self._post(self.VERIFY_URL, {
            'RefNum': callback.transaction_id,
            'TerminalNumber': self._terminal_number(),
        })
        if not isinstance(data, dict):
            return VerifyResult(success=False, message='invalid response')
        detail = data.get('TransactionDetail') or {}
        code = data.get('ResultCode')
        accepted = (data.get('Success') is True and code == 0) or code == ALREADY_VERIFIED_CODE
        if not accepted or not detail:
            return VerifyResult(success=False, message=str(data.get('ResultDescription') or code), raw=data)
        try:
            amount = int(detail.get('OrginalAmount') or 0)
        except (TypeError, ValueError):
            amount = 0
        return VerifyResult(
            success=True,
            amount=amount,
            transaction_id=str(detail.get('RefNum') or ''),
            rrn=str(detail.get('RRN') or ''),
            trace_no=str(detail.get('StraceNo') or ''),
            card_mask=str(detail.get('MaskedPan') or '')[:32],
            raw=data,
        )

    def reverse(self, payment):
        if not payment.transaction_id:
            return False
        try:
            _, data = self._post(self.REVERSE_URL, {
                'RefNum': payment.transaction_id,
                'TerminalNumber': self._terminal_number(),
            })
        except GatewayError:
            return False
        return isinstance(data, dict) and data.get('Success') is True
