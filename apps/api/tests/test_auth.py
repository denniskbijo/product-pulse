from app.auth import authenticate, create_access_token, decode_token
from app.config import Settings
from app.passwords import hash_password


def test_authenticate_roles():
    settings = Settings(
        jwt_secret="test-secret",
        admin_username="admin",
        admin_password_hash=hash_password("admin-pass"),
        user_username="viewer",
        user_password_hash=hash_password("viewer-pass"),
    )
    admin = authenticate("admin", "admin-pass", settings)
    user = authenticate("viewer", "viewer-pass", settings)
    bad = authenticate("admin", "wrong", settings)
    unknown = authenticate("nobody", "admin-pass", settings)
    assert admin is not None and admin.role == "admin"
    assert user is not None and user.role == "user"
    assert bad is None
    assert unknown is None


def test_token_roundtrip():
    settings = Settings(
        jwt_secret="test-secret",
        admin_username="admin",
        admin_password_hash=hash_password("admin-pass"),
    )
    admin = authenticate("admin", "admin-pass", settings)
    assert admin is not None
    token = create_access_token(admin, settings)
    decoded = decode_token(token, settings)
    assert decoded.username == "admin"
    assert decoded.role == "admin"


def test_plaintext_env_password_is_ignored():
    settings = Settings(
        jwt_secret="test-secret",
        admin_username="admin",
        admin_password="admin-pass",
        admin_password_hash="",
    )
    assert authenticate("admin", "admin-pass", settings) is None
