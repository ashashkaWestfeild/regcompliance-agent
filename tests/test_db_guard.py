"""The live-database guard (PROBLEMS_LOG P-058). No real database: psycopg.connect is replaced."""

import pytest

from regcomp import db

LIVE = "postgresql://user:secret@live-host.example/db"
D2 = "postgresql://user:secret@d2-host.example/db"
OTHER = "postgresql://user:secret@elsewhere.example/db"
ENV = {"REGCOMP_LIVE_HOST": "live-host.example", "REGCOMP_D2_HOST": "d2-host.example"}


def test_roles_come_from_the_host_labels():
    assert db.database_role(LIVE, ENV) == "live"
    assert db.database_role(D2, ENV) == "d2"
    assert db.database_role(OTHER, ENV) == "unlabelled"
    assert db.database_role(LIVE, {}) == "unlabelled"


def test_live_is_read_only_unless_allowed():
    assert db.live_read_only("live", ENV)
    assert not db.live_read_only("live", ENV | {"REGCOMP_ALLOW_LIVE": "1"})
    assert not db.live_read_only("d2", ENV)
    assert not db.live_read_only("unlabelled", ENV)


@pytest.mark.parametrize(
    ("url", "allow", "read_only", "banner"),
    [
        (LIVE, None, True, "database: live (read-only"),
        (LIVE, "1", False, "database: live (WRITES ALLOWED"),
        (D2, None, False, "database: d2"),
        (OTHER, None, False, "database: unlabelled"),
    ],
)
def test_connect_opens_live_read_only_and_says_where(
    monkeypatch, capsys, url, allow, read_only, banner
):
    seen = {}
    monkeypatch.setattr(db, "load_dotenv", lambda: None)
    monkeypatch.setattr(db, "_announced", set())
    monkeypatch.setattr(db.psycopg, "connect", lambda u, **kw: seen.update(kw) or "conn")
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("DATABASE_URL", url)
    if allow:
        monkeypatch.setenv("REGCOMP_ALLOW_LIVE", allow)
    else:
        monkeypatch.delenv("REGCOMP_ALLOW_LIVE", raising=False)
    assert db.connect() == "conn"
    assert ("default_transaction_read_only=on" in seen.get("options", "")) is read_only
    err = capsys.readouterr().err
    assert banner in err
    assert "secret" not in err  # never the credentials
