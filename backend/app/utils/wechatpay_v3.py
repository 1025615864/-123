from __future__ import annotations

import base64
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, cast

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_private_key


@dataclass(frozen=True)
class WeChatPayPlatformCert:
    serial_no: str
    pem: str
    expire_time: str | None = None


def load_rsa_private_key(private_key_pem: str) -> RSAPrivateKey:
    key = load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    return cast(RSAPrivateKey, key)


def load_rsa_public_key_from_cert_pem(cert_pem: str) -> RSAPublicKey:
    cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
    pub = cert.public_key()
    return cast(RSAPublicKey, pub)


def wechatpay_verify_signature(
    *,
    cert_pem: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    signature_b64: str,
) -> bool:
    try:
        signature = base64.b64decode(signature_b64)
    except Exception:
        return False

    message = timestamp.encode("utf-8") + b"\n" + nonce.encode("utf-8") + b"\n" + body + b"\n"
    pub_key = load_rsa_public_key_from_cert_pem(cert_pem)
    try:
        pub_key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def wechatpay_decrypt_resource(*, api_v3_key: str, nonce: str, associated_data: str, ciphertext: str) -> bytes:
    key_bytes = api_v3_key.encode("utf-8")
    if len(key_bytes) != 32:
        raise ValueError("WECHATPAY_API_V3_KEY must be 32 bytes")

    aesgcm = AESGCM(key_bytes)
    nonce_bytes = nonce.encode("utf-8")
    ad_bytes = associated_data.encode("utf-8") if associated_data is not None else b""
    cipher_bytes = base64.b64decode(ciphertext)
    return aesgcm.decrypt(nonce_bytes, cipher_bytes, ad_bytes)


def wechatpay_build_authorization(
    *,
    mch_id: str,
    serial_no: str,
    private_key_pem: str,
    method: str,
    url_path: str,
    body: str,
    timestamp: int | None = None,
    nonce_str: str | None = None,
) -> str:
    if timestamp is None:
        timestamp = int(time.time())
    if nonce_str is None:
        nonce_str = uuid.uuid4().hex

    message = f"{method}\n{url_path}\n{timestamp}\n{nonce_str}\n{body}\n".encode("utf-8")
    key = load_rsa_private_key(private_key_pem)
    signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    signature_b64 = base64.b64encode(signature).decode("utf-8")

    return (
        "WECHATPAY2-SHA256-RSA2048 "
        f'mchid="{mch_id}",' 
        f'nonce_str="{nonce_str}",' 
        f'signature="{signature_b64}",' 
        f'timestamp="{timestamp}",' 
        f'serial_no="{serial_no}"'
    )


async def fetch_platform_certificates(
    *,
    certificates_url: str,
    mch_id: str,
    mch_serial_no: str,
    mch_private_key_pem: str,
    api_v3_key: str,
    timeout_seconds: float = 10.0,
) -> list[WeChatPayPlatformCert]:
    url = certificates_url
    if "/v3/" in url:
        url_path = url.split(".com", 1)[-1]
        if not url_path.startswith("/"):
            url_path = "/" + url_path
    else:
        url_path = "/v3/certificates"

    authorization = wechatpay_build_authorization(
        mch_id=mch_id,
        serial_no=mch_serial_no,
        private_key_pem=mch_private_key_pem,
        method="GET",
        url_path=url_path,
        body="",
    )

    headers = {
        "Authorization": authorization,
        "Accept": "application/json",
        "User-Agent": "baixing-helper/1.0",
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        res = await client.get(url, headers=headers)
        res.raise_for_status()
        data_raw: object = res.json()

    if not isinstance(data_raw, dict):
        raise ValueError("wechatpay certificates response must be an object")
    data = cast(dict[str, Any], data_raw)
    items_raw = data.get("data")
    if not isinstance(items_raw, list):
        raise ValueError("wechatpay certificates response missing data list")

    out: list[WeChatPayPlatformCert] = []
    for item_obj in cast(list[object], items_raw):
        if not isinstance(item_obj, dict):
            continue
        item = cast(dict[str, Any], item_obj)
        serial = str(item.get("serial_no") or "").strip()
        expire_time = str(item.get("expire_time") or "").strip() or None
        enc = item.get("encrypt_certificate")
        if not serial or not isinstance(enc, dict):
            continue
        enc_dict = cast(dict[str, Any], enc)
        nonce = str(enc_dict.get("nonce") or "")
        ad = str(enc_dict.get("associated_data") or "")
        ciphertext = str(enc_dict.get("ciphertext") or "")
        if not nonce or not ciphertext:
            continue
        plain = wechatpay_decrypt_resource(
            api_v3_key=api_v3_key,
            nonce=nonce,
            associated_data=ad,
            ciphertext=ciphertext,
        )
        pem = plain.decode("utf-8")
        out.append(WeChatPayPlatformCert(serial_no=serial, pem=pem, expire_time=expire_time))

    return out


def dump_platform_certs_json(certs: list[WeChatPayPlatformCert]) -> str:
    payload = {
        "updated_at": int(time.time()),
        "certs": [
            {"serial_no": c.serial_no, "pem": c.pem, "expire_time": c.expire_time}
            for c in certs
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def load_platform_certs_json(raw: str) -> dict[str, WeChatPayPlatformCert]:
    s = str(raw or "").strip()
    if not s:
        return {}
    obj_raw: object = json.loads(s)
    if not isinstance(obj_raw, dict):
        return {}
    obj = cast(dict[str, Any], obj_raw)
    certs_raw = obj.get("certs")
    if not isinstance(certs_raw, list):
        return {}

    out: dict[str, WeChatPayPlatformCert] = {}
    for item_obj in cast(list[object], certs_raw):
        if not isinstance(item_obj, dict):
            continue
        item = cast(dict[str, Any], item_obj)
        serial = str(item.get("serial_no") or "").strip()
        pem = str(item.get("pem") or "")
        expire_time = str(item.get("expire_time") or "").strip() or None
        if not serial or not pem:
            continue
        out[serial] = WeChatPayPlatformCert(serial_no=serial, pem=pem, expire_time=expire_time)
    return out
