import os
import socket
import ssl
import traceback

import django
import requests
import urllib3

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.conf import settings

print("requests", requests.__version__, "urllib3", urllib3.__version__)
session = requests.Session()
session.trust_env = False
candidates = [
    "http://127.0.0.1:8000/payment/verify/",
    "https://kasrapublishing.ir/payment/verify/",
    "https://www.kasrapublishing.ir/payment/verify/",
    "https://kasra-pub.ir/payment/verify/",
    "https://www.kasra-pub.ir/payment/verify/",
]
for url in candidates:
    try:
        response = session.post(
            "https://sep.shaparak.ir/onlinepg/onlinepg",
            json={
                "action": "token",
                "TerminalId": settings.SEP_TERMINAL_ID,
                "Amount": 10000,
                "ResNum": "probe-resnum-1",
                "RedirectUrl": url,
            },
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=20,
        )
        data = response.json()
        print(url, "->", data.get("status"), data.get("errorCode"), data.get("errorDesc"), "token", bool(data.get("token")))
    except Exception as exc:
        print(url, "->", type(exc).__name__, str(exc)[:120])

print("proxy", {k: os.environ.get(k) for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]})
print("openssl", ssl.OPENSSL_VERSION)
host = "sep.shaparak.ir"
ctx = ssl.create_default_context()
body = b'{"action":"token","TerminalId":"1","Amount":10000,"ResNum":"1","RedirectUrl":"https://example.com/cb"}'
req = (
    b"POST /onlinepg/onlinepg HTTP/1.1\r\nHost: " + host.encode()
    + b"\r\nUser-Agent: Mozilla/5.0\r\nContent-Type: application/json\r\n"
    + b"Accept: application/json\r\nContent-Length: " + str(len(body)).encode()
    + b"\r\nConnection: close\r\n\r\n" + body
)
try:
    with socket.create_connection((host, 443), timeout=20) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ss:
            print("tls", ss.version(), ss.cipher()[0])
            ss.sendall(req)
            data = b""
            while True:
                chunk = ss.recv(4096)
                if not chunk:
                    break
                data += chunk
            print(data[:600].decode("utf-8", "replace"))
except Exception as exc:
    print(type(exc).__name__, exc)
