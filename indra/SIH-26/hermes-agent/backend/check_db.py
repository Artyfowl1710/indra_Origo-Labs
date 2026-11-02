import sqlite3
c = sqlite3.connect('data/workbench.db')
print("TABLES:")
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print("  ", r[0])
print("\nAPI_KEYS:")
for r in c.execute("SELECT key_id, owner, scope, revoked FROM api_keys"):
    print("  ", r)
print("\nMODELS:")
for r in c.execute("SELECT id, backend, model_type, status, local_path, vram_mb FROM model_records"):
    print("  ", r)
c.close()
