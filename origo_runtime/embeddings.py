"""Resident, CPU-only MiniLM encoder. Local files only; no download or remote code."""
import hashlib
import json
from pathlib import Path
import threading

MODEL_DIR = Path(__file__).resolve().parents[1] / "data/models/minilm"
_instance = None
_lock = threading.Lock()

class OfflineEncoder:
    def __init__(self, directory=MODEL_DIR):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.np = np
        directory = Path(directory)
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        for filename in ("model_quantized.onnx", "tokenizer.json"):
            if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != manifest["files"][filename]["sha256"]:
                raise ValueError("Offline embedding asset checksum mismatch")
        self.signature = manifest["files"]["model_quantized.onnx"]["sha256"]
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding()
        options = ort.SessionOptions(); options.intra_op_num_threads = 2; options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(directory / "model_quantized.onnx"), sess_options=options, providers=["CPUExecutionProvider"])
        self.lock = threading.Lock()

    def encode(self, texts):
        np = self.np; result = []
        with self.lock:
            for start in range(0, len(texts), 16):
                batch = self.tokenizer.encode_batch([text[:6000] for text in texts[start:start+16]])
                inputs = {"input_ids": np.array([e.ids for e in batch], dtype=np.int64),
                          "attention_mask": np.array([e.attention_mask for e in batch], dtype=np.int64),
                          "token_type_ids": np.array([e.type_ids for e in batch], dtype=np.int64)}
                accepted = {v.name for v in self.session.get_inputs()}
                hidden = self.session.run(None, {k:v for k,v in inputs.items() if k in accepted})[0]
                mask = inputs["attention_mask"][:, :, None]
                pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
                pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
                result.extend(pooled.astype(np.float32).tolist())
        return result

def encoder():
    global _instance
    with _lock:
        if _instance is None: _instance = OfflineEncoder()
        return _instance

def status():
    return {"model": "all-MiniLM-L6-v2 · int8", "dimensions":384, "offline":True,
            "installed": (MODEL_DIR / "manifest.json").is_file(), "resident":_instance is not None,
            "model_bytes":(MODEL_DIR / "model_quantized.onnx").stat().st_size if (MODEL_DIR / "model_quantized.onnx").exists() else 0}
