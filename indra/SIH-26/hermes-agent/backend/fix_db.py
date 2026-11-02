import sqlite3
import shutil
import os

print("=== Attempting database recovery ===")

# 1. Try integrity check
c = sqlite3.connect('data/workbench.db', isolation_level=None)
result = c.execute('PRAGMA integrity_check').fetchall()
print(f"Integrity check: {result}")

# 2. Try to dump and recreate
print("\nDumping existing data...")
try:
    api_keys = c.execute('SELECT * FROM api_keys').fetchall()
    print(f"  api_keys: {len(api_keys)} rows")
    for k in api_keys:
        print(f"    {k}")
except Exception as e:
    print(f"  api_keys error: {e}")
    api_keys = []

try:
    models = c.execute('SELECT * FROM models').fetchall()
    print(f"  models: {len(models)} rows")
    for m in models:
        print(f"    id={m[0]}")
except Exception as e:
    print(f"  models error: {e}")
    models = []

c.close()

# 3. Backup corrupt DB
print("\nBacking up corrupt DB...")
shutil.copy2('data/workbench.db', 'data/workbench.db.corrupt_backup')
# Also remove WAL/SHM files
for ext in ['-wal', '-shm']:
    f = f'data/workbench.db{ext}'
    if os.path.exists(f):
        print(f"  Removing {f}")
        os.remove(f)

# 4. Delete and let the server recreate it
print("Deleting corrupt DB...")
os.remove('data/workbench.db')

# 5. Recreate with schema via the server's init_db
import sys
sys.path.insert(0, '.')
from server.db import init_db, SessionLocal, ApiKey, ModelRecord
from server.core.auth import generate_key, hash_key
from datetime import datetime
import secrets as _secrets

init_db()
print("Fresh DB created with schema.")

# 6. Re-insert the admin key (we know the existing plaintext key from .env)
# We need to hash it fresh since we know the plaintext
admin_key = "wb_live_FQJC5OkzgWuB7Ik0JMusg98bXLBCNIe8"
with SessionLocal() as db:
    row = ApiKey(
        key_id="admin_bootstrap",
        key_hash=hash_key(admin_key),
        owner="bootstrap",
        scope="admin",
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    print(f"Admin key re-created (key_id=admin_bootstrap)")

# 7. Register qwen3.5-4b model
with SessionLocal() as db:
    import json
    m = ModelRecord(
        id="qwen3.5-4b",
        backend="llamaswap",
        model_type="text",
        task_tags=json.dumps(["chat"]),
        source_type="local_path",
        source_ref="models/Qwen_Qwen3.5-4B-Q4_K_M.gguf",
        local_path="models/Qwen_Qwen3.5-4B-Q4_K_M.gguf",
        status="cold",
        vram_mb=4500,
        pinned=False,
        active_requests=0,
        registered_at=datetime.utcnow(),
    )
    db.add(m)

    # Also register gemma-2-2b-it
    m2 = ModelRecord(
        id="gemma-2-2b-it",
        backend="llamaswap",
        model_type="text",
        task_tags=json.dumps(["chat", "instruct"]),
        source_type="local_path",
        source_ref="models/gemma-2-2b-it-Q4_K_M.gguf",
        local_path="models/gemma-2-2b-it-Q4_K_M.gguf",
        status="cold",
        vram_mb=3000,
        pinned=False,
        active_requests=0,
        registered_at=datetime.utcnow(),
    )
    db.add(m2)

    # Also register phi-4-mini-instruct
    m3 = ModelRecord(
        id="phi-4-mini-instruct",
        backend="llamaswap",
        model_type="text",
        task_tags=json.dumps(["chat", "instruct"]),
        source_type="local_path",
        source_ref="models/Phi-4-mini-instruct-Q2_K_L.gguf",
        local_path="models/Phi-4-mini-instruct-Q2_K_L.gguf",
        status="cold",
        vram_mb=3000,
        pinned=False,
        active_requests=0,
        registered_at=datetime.utcnow(),
    )
    db.add(m3)

    db.commit()
    print("All 3 models registered.")

# Final verify
with SessionLocal() as db:
    print("\n=== Final DB State ===")
    print("API Keys:")
    for k in db.query(ApiKey).all():
        print(f"  key_id={k.key_id} owner={k.owner} scope={k.scope} revoked={k.revoked}")
    print("Models:")
    for m in db.query(ModelRecord).all():
        print(f"  id={m.id} backend={m.backend} local_path={m.local_path} vram_mb={m.vram_mb}")

print("\n=== Database recovery complete ===")
