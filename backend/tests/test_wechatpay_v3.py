import base64
import datetime
import json
import re

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from app.utils.wechatpay_v3 import (
    WeChatPayPlatformCert,
    dump_platform_certs_json,
    fetch_platform_certificates,
    load_platform_certs_json,
    load_rsa_public_key_from_cert_pem,
    wechatpay_build_authorization,
    wechatpay_decrypt_resource,
    wechatpay_verify_signature,
)


def _gen_private_key_pem() -> tuple[rsa.RSAPrivateKey, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode("utf-8")
    return key, pem


def _gen_self_signed_cert_pem(key: rsa.RSAPrivateKey) -> str:
    subject = issuer = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "test")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    return cert.public_bytes(Encoding.PEM).decode("utf-8")


def test_wechatpay_decrypt_resource_roundtrip_and_key_length() -> None:
    api_v3_key = "k" * 32
    nonce = "n" * 12
    associated_data = "ad"
    plaintext = b"hello"

    aesgcm = AESGCM(api_v3_key.encode("utf-8"))
    cipher_bytes = aesgcm.encrypt(nonce.encode("utf-8"), plaintext, associated_data.encode("utf-8"))
    ciphertext = base64.b64encode(cipher_bytes).decode("utf-8")

    got = wechatpay_decrypt_resource(
        api_v3_key=api_v3_key,
        nonce=nonce,
        associated_data=associated_data,
        ciphertext=ciphertext,
    )
    assert got == plaintext

    with pytest.raises(ValueError):
        wechatpay_decrypt_resource(
            api_v3_key="short",
            nonce=nonce,
            associated_data=associated_data,
            ciphertext=ciphertext,
        )


def test_wechatpay_build_authorization_signature_is_valid() -> None:
    key, pem = _gen_private_key_pem()

    auth = wechatpay_build_authorization(
        mch_id="mch",
        serial_no="serial",
        private_key_pem=pem,
        method="GET",
        url_path="/v3/certificates",
        body="",
        timestamp=1700000000,
        nonce_str="nonce",
    )

    assert auth.startswith("WECHATPAY2-SHA256-RSA2048 ")

    m = re.search(r'signature="([^"]+)"', auth)
    assert m
    sig_b64 = m.group(1)
    sig = base64.b64decode(sig_b64)

    message = b"GET\n/v3/certificates\n1700000000\nnonce\n\n"
    key.public_key().verify(sig, message, padding.PKCS1v15(), hashes.SHA256())


def test_wechatpay_build_authorization_defaults_timestamp_and_nonce(monkeypatch: pytest.MonkeyPatch) -> None:
    _, pem = _gen_private_key_pem()

    monkeypatch.setattr("app.utils.wechatpay_v3.time.time", lambda: 1700000001)
    monkeypatch.setattr("app.utils.wechatpay_v3.uuid.uuid4", lambda: type("X", (), {"hex": "abc"})())

    auth = wechatpay_build_authorization(
        mch_id="mch",
        serial_no="serial",
        private_key_pem=pem,
        method="GET",
        url_path="/v3/certificates",
        body="",
    )
    assert 'timestamp="1700000001"' in auth
    assert 'nonce_str="abc"' in auth


def test_wechatpay_verify_signature_ok_and_bad_b64() -> None:
    key, _ = _gen_private_key_pem()
    cert_pem = _gen_self_signed_cert_pem(key)

    timestamp = "1700000000"
    nonce = "nonce"
    body = b"{}"
    message = timestamp.encode("utf-8") + b"\n" + nonce.encode("utf-8") + b"\n" + body + b"\n"
    sig = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.b64encode(sig).decode("utf-8")

    assert (
        wechatpay_verify_signature(
            cert_pem=cert_pem,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature_b64=sig_b64,
        )
        is True
    )

    assert (
        wechatpay_verify_signature(
            cert_pem=cert_pem,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature_b64="not-base64***",
        )
        is False
    )


def test_wechatpay_verify_signature_verify_failed_returns_false() -> None:
    key, _ = _gen_private_key_pem()
    cert_pem = _gen_self_signed_cert_pem(key)

    timestamp = "1700000000"
    nonce = "nonce"
    body = b"{}"
    message = timestamp.encode("utf-8") + b"\n" + nonce.encode("utf-8") + b"\n" + body + b"\n"
    sig = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.b64encode(sig).decode("utf-8")

    assert (
        wechatpay_verify_signature(
            cert_pem=cert_pem,
            timestamp=timestamp,
            nonce=nonce,
            body=b"{\"x\":1}",
            signature_b64=sig_b64,
        )
        is False
    )


def test_load_rsa_public_key_from_cert_pem() -> None:
    key, _ = _gen_private_key_pem()
    cert_pem = _gen_self_signed_cert_pem(key)
    pub = load_rsa_public_key_from_cert_pem(cert_pem)

    msg = b"hi"
    sig = key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    pub.verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())


def test_dump_and_load_platform_certs_json() -> None:
    certs = [WeChatPayPlatformCert(serial_no="s", pem="pem", expire_time=None)]
    raw = dump_platform_certs_json(certs)
    mapping = load_platform_certs_json(raw)
    assert mapping["s"].pem == "pem"

    assert load_platform_certs_json("") == {}

    assert load_platform_certs_json("[]") == {}

    raw2 = json.dumps(
        {
            "updated_at": 1,
            "certs": [
                "x",
                {"serial_no": "", "pem": "pem"},
                {"serial_no": "S2", "pem": ""},
                {"serial_no": "OK", "pem": "pem", "expire_time": "t"},
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    mapping2 = load_platform_certs_json(raw2)
    assert list(mapping2.keys()) == ["OK"]

    with pytest.raises(json.JSONDecodeError):
        load_platform_certs_json("not-json")


@pytest.mark.asyncio
async def test_fetch_platform_certificates_url_path_without_com_prefix_slash_and_skips_missing_nonce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {}

    def _fake_build_auth(**kwargs):
        called["url_path"] = kwargs.get("url_path")
        assert str(kwargs.get("url_path") or "").startswith("/")
        return "AUTH"

    def _fake_decrypt_resource(**_kwargs):
        return b"CERT_PEM"

    monkeypatch.setattr("app.utils.wechatpay_v3.wechatpay_build_authorization", _fake_build_auth)
    monkeypatch.setattr("app.utils.wechatpay_v3.wechatpay_decrypt_resource", _fake_decrypt_resource)

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {
                        "serial_no": "SER",
                        "expire_time": "T",
                        "encrypt_certificate": {
                            "nonce": "n",
                            "associated_data": "ad",
                            "ciphertext": "c",
                        },
                    },
                    {
                        "serial_no": "SER2",
                        "expire_time": "T",
                        "encrypt_certificate": {
                            "nonce": "",
                            "associated_data": "ad",
                            "ciphertext": "c",
                        },
                    },
                ]
            }

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            called["url"] = url
            called["headers"] = headers
            return _Resp()

    monkeypatch.setattr("app.utils.wechatpay_v3.httpx.AsyncClient", _Client)

    out = await fetch_platform_certificates(
        certificates_url="https://api.mch.weixin.qq.cn/v3/certificates",
        mch_id="m",
        mch_serial_no="s",
        mch_private_key_pem="k",
        api_v3_key="x" * 32,
    )

    assert called["headers"]["Authorization"] == "AUTH"
    assert len(out) == 1
    assert out[0].serial_no == "SER"


@pytest.mark.asyncio
async def test_fetch_platform_certificates_parses_items_and_url_path(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def _fake_build_auth(**_kwargs):
        return "AUTH"

    def _fake_decrypt_resource(**_kwargs):
        return b"CERT_PEM"

    monkeypatch.setattr("app.utils.wechatpay_v3.wechatpay_build_authorization", _fake_build_auth)
    monkeypatch.setattr("app.utils.wechatpay_v3.wechatpay_decrypt_resource", _fake_decrypt_resource)

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {
                        "serial_no": "SER",
                        "expire_time": "T",
                        "encrypt_certificate": {
                            "nonce": "n",
                            "associated_data": "ad",
                            "ciphertext": "c",
                        },
                    },
                    {"serial_no": "", "encrypt_certificate": {}},
                    "bad",
                ]
            }

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            called["url"] = url
            called["headers"] = headers
            return _Resp()

    monkeypatch.setattr("app.utils.wechatpay_v3.httpx.AsyncClient", _Client)

    out = await fetch_platform_certificates(
        certificates_url="https://api.mch.weixin.qq.com/v3/certificates",
        mch_id="m",
        mch_serial_no="s",
        mch_private_key_pem="k",
        api_v3_key="x" * 32,
    )

    assert called["headers"]["Authorization"] == "AUTH"
    assert called["url"].endswith("/v3/certificates")
    assert len(out) == 1
    assert out[0].serial_no == "SER"
    assert out[0].pem == "CERT_PEM"


@pytest.mark.asyncio
async def test_fetch_platform_certificates_default_url_path_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_build_auth(**kwargs):
        assert kwargs["url_path"] == "/v3/certificates"
        return "AUTH"

    monkeypatch.setattr("app.utils.wechatpay_v3.wechatpay_build_authorization", _fake_build_auth)

    class _Resp1:
        def raise_for_status(self):
            return None

        def json(self):
            return []

    class _Client1:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return _Resp1()

    monkeypatch.setattr("app.utils.wechatpay_v3.httpx.AsyncClient", _Client1)

    with pytest.raises(ValueError):
        await fetch_platform_certificates(
            certificates_url="https://example.com/certs",
            mch_id="m",
            mch_serial_no="s",
            mch_private_key_pem="k",
            api_v3_key="x" * 32,
        )

    class _Resp2:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": "bad"}

    class _Client2(_Client1):
        async def get(self, url, headers):
            return _Resp2()

    monkeypatch.setattr("app.utils.wechatpay_v3.httpx.AsyncClient", _Client2)

    with pytest.raises(ValueError):
        await fetch_platform_certificates(
            certificates_url="https://example.com/certs",
            mch_id="m",
            mch_serial_no="s",
            mch_private_key_pem="k",
            api_v3_key="x" * 32,
        )
