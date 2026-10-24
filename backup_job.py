import os
import zipfile
import psycopg2
import pandas as pd
from datetime import datetime

def main():
    # সরাসরি environment থেকে DB_URL ফেচ করা
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise ValueError("DB_URL environment variable is not set.")

    # কানেকশন তৈরি
    conn = psycopg2.connect(db_url, connect_timeout=30)
    
    # পাবলিক স্কিমার সব টেবিল বের করা
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema='public' AND table_type='BASE TABLE'
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        tables = [row[0] for row in cur.fetchall()]

    date_str = datetime.now().strftime("%Y-%m-%d")
    zip_filename = "backup_" + date_str + ".zip"

    # টেবিলগুলোকে CSV হিসেবে জিপ ফাইলে ডাম্প করা
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zf:
        for table in tables:
            df = pd.read_sql(f'SELECT * FROM "{table}"', conn)
            csv_data = df.to_csv(index=False)
            zf.writestr(f"{table}.csv", csv_data)

    conn.close()
    print(f"Backup successfully created: {zip_filename}")

if __name__ == "__main__":
    main()
