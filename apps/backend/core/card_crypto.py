"""Authenticated encryption for Demo card numbers.

The card number is not a real payment credential.  It is still treated as a
secret: only ciphertext is persisted and the per-environment key never enters
the database, API response, audit log, or Git.
"""

import base64
import binascii
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.errors import DomainError


def _key(encoded: str) -> bytes:
    try:
        value = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise DomainError(
            "CARD_ENCRYPTION_UNCONFIGURED",
            "卡片加密密钥未正确配置",
            503,
        ) from exc
    if len(value) != 32:
        raise DomainError(
            "CARD_ENCRYPTION_UNCONFIGURED",
            "卡片加密密钥必须是 32 字节的 URL-safe Base64",
            503,
        )
    return value


def encrypt_pan(encoded_key: str, card_id: str, pan: str) -> str:
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_key(encoded_key)).encrypt(
        nonce,
        pan.encode("ascii"),
        card_id.encode("ascii"),
    )
    return "v1." + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def validate_card_key(encoded_key: str) -> None:
    _key(encoded_key)


def decrypt_pan(encoded_key: str, card_id: str, value: str) -> str:
    if not value.startswith("v1."):
        raise DomainError("CARD_DATA_INVALID", "卡片密文版本无法识别", 500)
    try:
        raw = base64.urlsafe_b64decode(value[3:].encode("ascii"))
        plaintext = AESGCM(_key(encoded_key)).decrypt(
            raw[:12],
            raw[12:],
            card_id.encode("ascii"),
        )
        return plaintext.decode("ascii")
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError("CARD_DATA_INVALID", "卡片密文校验失败", 500) from exc
