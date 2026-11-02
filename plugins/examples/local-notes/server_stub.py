"""Safe demo service for the local-notes plugin contract.

Run explicitly with `python plugins/examples/local-notes/server_stub.py`.
It binds only to 127.0.0.1:9911, holds a tiny in-memory note set, and exposes a
read-only POST /search endpoint. It never reads arbitrary paths or writes state.
"""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOTES = [
    {"id": "n1", "title": "Research planning", "text": "Write a hypothesis before running an experiment; save the baseline and evaluation setup."},
    {"id": "n2", "title": "Local models", "text": "Record model version, quantization, server parameters, context size and hardware when benchmarking."},
    {"id": "n3", "title": "Safety review", "text": "Review file diffs and tool permissions; treat remote content as untrusted evidence."},
]

class Handler(BaseHTTPRequestHandler):
    server_version = "IndraLocalNotesDemo/1.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        # Avoid logging query contents; keep request diagnostics minimal.
        print(f"[local-notes-demo] {self.address_string()} {self.command} {self.path.split('?')[0]}")

    def _send(self, status: int, value: dict):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/search":
            self._send(404, {"error": "not found"}); return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if not 0 <= length <= 4096:
            self._send(413, {"error": "request body must be at most 4 KB"}); return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, {"error": "invalid JSON"}); return
        if not isinstance(body, dict) or set(body) - {"query", "limit"}:
            self._send(400, {"error": "expected query and optional limit"}); return
        query = body.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > 300:
            self._send(400, {"error": "query must be 1–300 characters"}); return
        limit = body.get("limit", 5)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit not in {3, 5, 8}:
            self._send(400, {"error": "limit must be 3, 5, or 8"}); return
        terms = query.casefold().split()
        ranked = sorted(NOTES, key=lambda note: sum(term in (note["title"] + " " + note["text"]).casefold() for term in terms), reverse=True)
        self._send(200, {"query": query, "results": ranked[:limit], "read_only": True, "demo": True})

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "service": "local-notes-demo"})
        else:
            self._send(404, {"error": "not found"})

    def do_PUT(self): self._send(405, {"error": "mutations are not supported"})
    def do_PATCH(self): self._send(405, {"error": "mutations are not supported"})
    def do_DELETE(self): self._send(405, {"error": "mutations are not supported"})

if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 9911), Handler)
    server.daemon_threads = True
    print("Local notes demo listening at http://127.0.0.1:9911; Ctrl+C to stop")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
