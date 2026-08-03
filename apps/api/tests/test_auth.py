from app.auth import authenticate, create_access_token, decode_token
from app.config import Settings


def test_authenticate_roles():
    settings = Settings(
        jwt_secret="test-secret",
        admin_username="admin",
        admin_password="admin-pass",
        user_username="viewer",
        user_password="viewer-pass",
    )
    admin = authenticate("admin", "admin-pass", settings)
    user = authenticate("viewer", "viewer-pass", settings)
    bad = authenticate("admin", "wrong", settings)
    assert admin is not None and admin.role == "admin"
    assert user is not None and user.role == "user"
    assert bad is None


def test_token_roundtrip():
    settings = Settings(
        jwt_secret="test-secret",
        admin_username="admin",
        admin_password="admin-pass",
    )
    admin = authenticate("admin", "admin-pass", settings)
    assert admin is not None
    token = create_access_token(admin, settings)
    decoded = decode_token(token, settings)
    assert decoded.username == "admin"
    assert decoded.role == "admin"
