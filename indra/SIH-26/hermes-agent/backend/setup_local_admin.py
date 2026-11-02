from pathlib import Path
from dotenv import dotenv_values,set_key
from server.db import init_db,SessionLocal,ApiKey
from server.core.auth import hash_key
import secrets
init_db()
root=Path.cwd().parents[1]
key=dotenv_values('.env').get('WORKBENCH_API_KEY')
if not key or len(key)<16: raise RuntimeError('Existing admin credential missing')
with SessionLocal() as db:
    if not db.query(ApiKey).filter_by(scope='admin',revoked=False).first():
        db.add(ApiKey(key_id=secrets.token_hex(8),key_hash=hash_key(key),owner='local-admin',scope='admin'));db.commit()
for name in ['WORKBENCH_API_KEY','OPENAI_API_KEY']:set_key(str(root/'.env'),name,key)
set_key(str(root/'.env'),'WORKBENCH_API_BASE','http://127.0.0.1:8000')
print('Existing backend admin credential configured; no user key created.')
