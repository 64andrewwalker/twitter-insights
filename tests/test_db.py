from ti.db import init_db, rebuild_fts
from ti.taxonomy import TAXONOMY, ALL_TAGS


def test_schema_creates_all_tables(db):
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"users", "tweets", "tags", "tweet_tags", "import_log", "metadata"} <= tables


def test_fts_table_exists(db):
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "tweets_fts" in tables


def test_tags_seeded(db):
    count = db.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    assert count == len(ALL_TAGS)
    assert count == 32


def test_tags_have_correct_categories(db):
    rows = db.execute("SELECT name, category FROM tags").fetchall()
    for row in rows:
        assert row["category"] in TAXONOMY
        assert row["name"] in TAXONOMY[row["category"]]


def test_idempotent_init(db):
    init_db(db)
    init_db(db)
    count = db.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    assert count == 32


def test_rebuild_fts_empty(db):
    rebuild_fts(db)
