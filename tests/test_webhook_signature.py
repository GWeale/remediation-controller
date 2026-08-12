from app.webhook import verify_signature
from tests.conftest import sign


def test_valid_signature_accepted():
    body = b'{"hello": "world"}'
    assert verify_signature("secret", body, sign(body, "secret"))


def test_wrong_secret_rejected():
    body = b'{"hello": "world"}'
    assert not verify_signature("secret", body, sign(body, "other-secret"))


def test_tampered_body_rejected():
    assert not verify_signature("secret", b"tampered", sign(b"original", "secret"))


def test_missing_or_malformed_header_rejected():
    assert not verify_signature("secret", b"x", None)
    assert not verify_signature("secret", b"x", "")
    assert not verify_signature("secret", b"x", "sha1=abcdef")


def test_empty_secret_rejected():
    body = b"x"
    assert not verify_signature("", body, sign(body, ""))
