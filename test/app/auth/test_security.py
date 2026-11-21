from __future__ import annotations

from app.auth.security import hash_password, verify_password


def test__hash_password_does_not_store_plaintext() -> None:
    assert hash_password("secret123") != "secret123"


def test__verify_password_accepts_correct_password() -> None:
    hashed = hash_password("secret123")

    assert verify_password("secret123", hashed) is True


def test__verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("secret123")

    assert verify_password("wrong-password", hashed) is False
