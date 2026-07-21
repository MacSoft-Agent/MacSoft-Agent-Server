from __future__ import annotations

from macsoft.config import load_config
from macsoft.db import connect_db, init_db


def main() -> None:
    config = load_config()
    init_db(config)
    conn = connect_db(config)

    try:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

        print("DB tables:")
        for row in rows:
            print("-", row["name"])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
