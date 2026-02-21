"""Query functions: FTS search, tag filter, author filter, etc."""

import sqlite3

_BASE_SELECT = """
    SELECT t.*, u.screen_name, u.name,
           GROUP_CONCAT(tg.name) as tags
    FROM tweets t
    JOIN users u ON t.user_id = u.user_id
    LEFT JOIN tweet_tags tt ON t.id = tt.tweet_id
    LEFT JOIN tags tg ON tt.tag_id = tg.id
"""

_GROUP_BY = "GROUP BY t.id"


def fts_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    offset: int = 0,
    sort: str = "relevant",
) -> tuple[list[dict], int]:
    count_row = conn.execute(
        "SELECT COUNT(*) FROM tweets_fts WHERE tweets_fts MATCH ?",
        (query,),
    ).fetchone()
    total = count_row[0]

    if sort == "recent":
        order = "t.created_at DESC"
    elif sort == "popular":
        order = "(t.bookmark_count + t.favorite_count) DESC"
    else:
        order = "rank"

    rows = conn.execute(
        f"""SELECT t.*, u.screen_name, u.name,
                   GROUP_CONCAT(tg.name) as tags,
                   tweets_fts.rank as rank
            FROM tweets_fts
            JOIN tweets t ON tweets_fts.rowid = t.rowid
            JOIN users u ON t.user_id = u.user_id
            LEFT JOIN tweet_tags tt ON t.id = tt.tweet_id
            LEFT JOIN tags tg ON tt.tag_id = tg.id
            WHERE tweets_fts MATCH ?
            {_GROUP_BY}
            ORDER BY {order}
            LIMIT ? OFFSET ?""",
        (query, limit, offset),
    ).fetchall()

    return [dict(r) for r in rows], total


def by_tag(
    conn: sqlite3.Connection,
    tag_name: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    count_row = conn.execute(
        """SELECT COUNT(DISTINCT t.id)
           FROM tweets t
           JOIN tweet_tags tt ON t.id = tt.tweet_id
           JOIN tags tg ON tt.tag_id = tg.id
           WHERE tg.name = ? OR t.primary_tag = ?""",
        (tag_name, tag_name),
    ).fetchone()
    total = count_row[0]

    rows = conn.execute(
        f"""{_BASE_SELECT}
            WHERE tg.name = ? OR t.primary_tag = ?
            {_GROUP_BY}
            ORDER BY t.created_at DESC
            LIMIT ? OFFSET ?""",
        (tag_name, tag_name, limit, offset),
    ).fetchall()

    return [dict(r) for r in rows], total


def by_author(
    conn: sqlite3.Connection,
    screen_name: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    screen_name = screen_name.lstrip("@")
    count_row = conn.execute(
        """SELECT COUNT(*) FROM tweets t
           JOIN users u ON t.user_id = u.user_id
           WHERE u.screen_name = ?""",
        (screen_name,),
    ).fetchone()
    total = count_row[0]

    rows = conn.execute(
        f"""{_BASE_SELECT}
            WHERE u.screen_name = ?
            {_GROUP_BY}
            ORDER BY t.created_at DESC
            LIMIT ? OFFSET ?""",
        (screen_name, limit, offset),
    ).fetchall()

    return [dict(r) for r in rows], total


def show_tweet(conn: sqlite3.Connection, tweet_id: str) -> dict | None:
    row = conn.execute(
        f"""{_BASE_SELECT}
            WHERE t.id = ?
            {_GROUP_BY}""",
        (tweet_id,),
    ).fetchone()
    return dict(row) if row else None


def latest_tweets(
    conn: sqlite3.Connection,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    total = conn.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
    rows = conn.execute(
        f"""{_BASE_SELECT}
            {_GROUP_BY}
            ORDER BY t.created_at DESC
            LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows], total


def list_tags(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT tg.name, tg.category, COUNT(tt.tweet_id) as count
           FROM tags tg
           LEFT JOIN tweet_tags tt ON tg.id = tt.tag_id
           GROUP BY tg.id
           ORDER BY count DESC, tg.category, tg.name"""
    ).fetchall()
    return [dict(r) for r in rows]
