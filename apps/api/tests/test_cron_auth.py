from app.routers.cron import _authorized


def test_cron_auth_accepts_matching_bearer():
    assert _authorized("Bearer secret-token", "secret-token") is True


def test_cron_auth_rejects_wrong_or_missing():
    assert _authorized("Bearer wrong", "secret-token") is False
    assert _authorized(None, "secret-token") is False
    assert _authorized("secret-token", "secret-token") is False
    assert _authorized("Bearer secret-token", "") is False
