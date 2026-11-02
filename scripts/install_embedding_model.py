"""Explicit one-time download. Runtime embedding never accesses the network."""
import hashlib
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
REPO = "Xenova/all-MiniLM-L6-v2"

def main():
    target = ROOT / "data/models/minilm"
    target.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=90, follow_redirects=True, trust_env=False) as client:
        response = client.get(f"https://huggingface.co/api/models/{REPO}?blobs=true")
        response.raise_for_status(); info = response.json(); revision = info["sha"]
        manifest = {"repository": REPO, "revision": revision, "files": {}}
        for name in ("onnx/model_quantized.onnx", "tokenizer.json", "config.json"):
            entry = next(item for item in info["siblings"] if item["rfilename"] == name)
            filename = name.rsplit("/", 1)[-1]
            destination = target / filename
            digest = hashlib.sha256()
            temporary = destination.with_suffix(destination.suffix + ".part")
            total = 0
            with client.stream("GET", f"https://huggingface.co/{REPO}/resolve/{revision}/{name}") as download:
                download.raise_for_status()
                with temporary.open("wb") as stream:
                    for block in download.iter_bytes():
                        total += len(block)
                        if total > 40 * 1024 * 1024: raise ValueError("Unexpected model asset size")
                        digest.update(block); stream.write(block)
            expected = (entry.get("lfs") or {}).get("sha256")
            if expected and expected != digest.hexdigest(): raise ValueError("Model asset checksum mismatch")
            temporary.replace(destination)
            manifest["files"][filename] = {"sha256": digest.hexdigest(), "bytes": total}
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest), flush=True)

if __name__ == "__main__": main()
