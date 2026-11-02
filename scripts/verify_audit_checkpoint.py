"""Verify a ledger against an independently retained, signed checkpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from origo_runtime.audit import canonical
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def verify(database,checkpoint):
    expected={key:checkpoint[key] for key in ("count","head","public_key")}
    public=Ed25519PublicKey.from_public_bytes(bytes.fromhex(checkpoint["public_key"]))
    public.verify(bytes.fromhex(checkpoint["checkpoint_signature"]),canonical(expected))
    previous="0"*64; count=0; anchored=expected["count"]==0 and expected["head"]==previous
    # Verification must never initialize a missing ledger or change its journal.
    db=sqlite3.connect(Path(database).resolve().as_uri()+"?mode=ro",uri=True)
    try:
        for seq,event,digest,signature in db.execute("SELECT seq,event,digest,signature FROM events ORDER BY seq"):
            row=json.loads(event)
            if seq!=count+1 or row["seq"]!=seq or row["previous"]!=previous or hashlib.sha256(canonical(row)).hexdigest()!=digest: raise ValueError("Audit chain was modified")
            public.verify(bytes.fromhex(signature),bytes.fromhex(digest))
            count+=1; previous=digest
            if count==expected["count"]: anchored=digest==expected["head"]
    finally: db.close()
    if not anchored or count<expected["count"]: raise ValueError("Retained checkpoint does not match the ledger")
    return {"valid":True,"events":count,"checkpoint_events":expected["count"]}

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--home",type=Path,required=True);parser.add_argument("--checkpoint",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(verify(args.home/"provenance/events.sqlite3",json.loads(args.checkpoint.read_text(encoding="utf-8")))))
