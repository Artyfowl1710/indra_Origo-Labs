import os
import urllib.request
import zipfile
import shutil
import json

print("Fetching latest qdrant release...")
response = urllib.request.urlopen('https://api.github.com/repos/qdrant/qdrant/releases/latest')
data = json.loads(response.read())
tag = data['tag_name']

print(f"Downloading qdrant {tag}...")
qdrant_zip = "qdrant-x86_64-pc-windows-msvc.zip"
qdrant_url = f"https://github.com/qdrant/qdrant/releases/download/{tag}/{qdrant_zip}"
urllib.request.urlretrieve(qdrant_url, qdrant_zip)

print("Extracting qdrant...")
with zipfile.ZipFile(qdrant_zip, 'r') as zip_ref:
    zip_ref.extractall("temp_qdrant")

qdrant_exe = os.path.join("temp_qdrant", "qdrant.exe")
dest = os.path.join("venv", "Scripts", "qdrant.exe")

print(f"Moving to {dest}...")
shutil.move(qdrant_exe, dest)

print("Cleaning up...")
os.remove(qdrant_zip)
shutil.rmtree("temp_qdrant")

print("Done! qdrant is installed.")
