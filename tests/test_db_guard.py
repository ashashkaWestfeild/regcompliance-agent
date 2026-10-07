"""The live-database guard (PROBLEMS_LOG P-058). No real database: psycopg.connect is replaced."""

import pytest

from regcomp import db

LIVE = "postgresql://user:secret@live-host.example/db"
D2 = "postgresql://user:secret@d2-host.example/db"
OTHER = "postgresql://user:secret@elsewhere.example/db"
LOCAL = "postgresql://regcomp:local_only@localhost:5432/regcomp"
ENV = {"REGCOMP_LIVE_HOST": "live-host.example", "REGCOMP_D2_HOST": "d2-host.example"}


def test_roles_come_from_the_host_labels():
    assert db.database_role(LIVE, ENV) == "live"
    assert db.database_role(D2, ENV) == "d2"
    assert db.database_role(OTHER, ENV) == "unlabelled"
    assert db.database_role(LIVE, {}) == "unlabelled"
    assert db.database_role(LOCAL, ENV) == "local"


def test_a_pooler_host_or_the_live_database_name_is_still_live():
    neon = {
        "REGCOMP_LIVE_HOST": "ep-tooth-1.c-3.aws.neon.tech",
        "REGCOMP_D2_HOST": "ep-boat-2.c-3.aws.neon.tech",
    }
    assert (
        db.database_role("postgresql://u:p@ep-tooth-1-pooler.c-3.aws.neon.tech/neondb", neon)
        == "live"
    )
    by_name = neon | {"REGCOMP_LIVE_DB": "neondb"}
    assert db.database_role("postgresql://u:p@ep-new-3.c-3.aws.neon.tech/neondb", by_name) == "live"
    # the d2 copy keeps its role even though its database has the same name
    assert (
        db.database_role("postgresql://u:p@ep-boat-2-pooler.c-3.aws.neon.tech/neondb", by_name)
        == "d2"
    )
    assert (
        db.database_role("postgresql://u:p@ep-new-3.c-3.aws.neon.tech/other", by_name)
        == "unlabelled"
    )


def test_live_and_unlabelled_hosts_are_read_only_unless_allowed():
    assert db.read_only("live", ENV)
    assert not db.read_only("live", ENV | {"REGCOMP_ALLOW_LIVE": "1"})
    assert db.read_only("unlabelled", ENV)  # fails closed: a copied .env without labels
    assert not db.read_only("unlabelled", ENV | {"REGCOMP_ALLOW_UNLABELLED": "1"})
    assert not db.read_only("d2", ENV)
    assert not db.read_only("local", ENV)  # the docker-compose database


@pytest.mark.parametrize(
    ("url", "allow", "read_only", "banner"),
    [
        (LIVE, None, True, "database: live (read-only"),
        (LIVE, "1", False, "database: live (WRITES ALLOWED"),
        (D2, None, False, "database: d2"),
        (OTHER, None, True, "database: unlabelled (elsewhere.example, no label; read-only"),
        (LOCAL, None, False, "database: local"),
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
    monkeypatch.delenv("REGCOMP_ALLOW_UNLABELLED", raising=False)
    assert db.connect() == "conn"
    assert ("default_transaction_read_only=on" in seen.get("options", "")) is read_only
    err = capsys.readouterr().err
    assert banner in err
    assert "secret" not in err  # never the credentials
