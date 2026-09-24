import sqlite3
import json

conn = sqlite3.connect("data/vinalex.db")
c = conn.cursor()

c.execute("SELECT COUNT(*), COUNT(DISTINCT slug) FROM procedures")
row = c.fetchone()
print(f"Total rows: {row[0]}, Distinct slugs: {row[1]}")

c.execute("SELECT slug, title FROM procedures WHERE documents IS NULL OR documents = '' OR documents = '[]'")
empty_docs = c.fetchall()
print(f"Procedures with empty documents: {len(empty_docs)}")

c.execute("SELECT slug, title FROM procedures WHERE steps IS NULL OR steps = '' OR steps = '[]'")
empty_steps = c.fetchall()
print(f"Procedures with empty steps: {len(empty_steps)}")

c.execute("SELECT slug, title, length(documents), length(steps) FROM procedures LIMIT 5")
for r in c.fetchall():
    print("Sample:", r)

conn.close()
