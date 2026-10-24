"""Daily database backup (run by GitHub Actions - see daily_backup.yml).

Writes backup_YYYY-MM-DD.zip with ONE CSV per public table, exactly like the app's own
"Backup" button, so the ZIP can be restored from the app's restore screen unchanged.
Needs only the DB_URL environment variable (same value as DB_URL in the Streamlit secrets).
"""
import csv
import datetime as dt
import io
import os
import sys
import zipfile

import psycopg2

CHUNK = 5000


def main():
    db_url = os.environ.get("DB_URL", "").strip()
    if not db_url:
        sys.exit("DB_URL is not set (GitHub: Settings > Secrets and variables > Actions > New repository secret).")

    conn = psycopg2.connect(db_url, connect_timeout=30)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name")
    tables = [r[0] for r in cur.fetchall()]
    if "inventory" not in tables or "transactions" not in tables:
        sys.exit(f"Unexpected database: inventory/transactions table not found (found: {tables}).")

    dhaka = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=6)
    path = f"backup_{dhaka:%Y-%m-%d}.zip"
    rows_total = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for t in tables:
            cur.execute(f'SELECT * FROM "{t}"')
            cols = [d[0] for d in cur.description]
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(cols)
            while True:
                chunk = cur.fetchmany(CHUNK)
                if not chunk:
                    break
                w.writerows(chunk)
                rows_total += len(chunk)
            z.writestr(f"{t}.csv", buf.getvalue())
    conn.close()

    # Sanity check: the zip must be readable and hold every table.
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        names = {n[:-4] for n in z.namelist()}
    if bad or names != set(tables):
        sys.exit("Backup verification failed - zip is incomplete.")
    print(f"OK: {path} - {len(tables)} tables, {rows_total} rows, {os.path.getsize(path) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
