from plantguard_api.security import hash_password, verify_password


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first != second
    assert "correct horse battery staple" not in first
    assert verify_password("correct horse battery staple", first) is True
    assert verify_password("wrong password", first) is False


def test_password_verification_rejects_legacy_and_malformed_values():
    assert verify_password("password", None) is False
    assert verify_password("password", "not-a-password-hash") is False
    assert verify_password("password", "unknown$1$00$00") is False
