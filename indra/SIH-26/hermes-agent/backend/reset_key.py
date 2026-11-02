import sqlite3
conn = sqlite3.connect('data/workbench.db')
conn.execute("DELETE FROM api_keys")
conn.commit()
conn.close()
