"""Bounded document extraction worker, run in a short-lived isolated Python process."""
import json
from pathlib import Path
import sys
import zipfile

def extract(path):
    suffix = path.suffix.lower()
    if path.stat().st_size > 7*1024*1024: raise ValueError("Document exceeds 7 MiB")
    if suffix in {".docx", ".xlsx", ".pptx"}:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries)>10000 or sum(e.file_size for e in entries)>64*1024*1024: raise ValueError("Expanded document too large")
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path)); parts = []
        for i, page in enumerate(reader.pages):
            if i>=200: break
            parts.append(f"[Page {i+1}]\n{(page.extract_text() or '')[:20000]}")
            if sum(map(len,parts))>1_000_000: break
        return "\n\n".join(parts)[:1_000_000]
    # Extract XML rather than executing document macros, links or embedded objects.
    from xml.etree import ElementTree as ET
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n in {"word/document.xml","xl/sharedStrings.xml"} or n.startswith("ppt/slides/slide") and n.endswith(".xml") or n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
        parts=[]
        for name in sorted(names)[:300]:
            data=archive.read(name)
            if b"<!DOCTYPE" in data or b"<!ENTITY" in data: raise ValueError("Document XML declarations are not supported")
            root = ET.fromstring(data)
            parts.append(" ".join(node.text for node in root.iter() if node.text and node.tag.rsplit('}',1)[-1] in {"t","v"}))
            if sum(map(len,parts))>1_000_000: break
        return "\n\n".join(parts)[:1_000_000]

if __name__ == "__main__":
    try: print(json.dumps({"text":extract(Path(sys.argv[1]))}))
    except Exception as error: print(json.dumps({"error":type(error).__name__})); raise SystemExit(1)
