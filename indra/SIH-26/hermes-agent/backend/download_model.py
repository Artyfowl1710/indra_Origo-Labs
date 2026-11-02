import os
import urllib.request
import sys

MODELS_DIR = "models"
os.makedirs(MODELS_DIR, exist_ok=True)

MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_FILE = os.path.join(MODELS_DIR, "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf")

print(f"Downloading Qwen2.5-1.5B to {MODEL_FILE}...")
# Minimal progress reporter
def reporthook(count, block_size, total_size):
    if total_size > 0:
        percent = int(count * block_size * 100 / total_size)
        sys.stdout.write(f"\rDownloading... {percent}%")
        sys.stdout.flush()

urllib.request.urlretrieve(MODEL_URL, MODEL_FILE, reporthook)
print("\nDownload complete!")
