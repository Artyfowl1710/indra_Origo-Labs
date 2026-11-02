"""Real SDK requests prove model, endpoint and credential routing without cloud calls."""
import asyncio
import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import yaml

from agent import auxiliary_client as aux
from tools import vision_tools as vision


@pytest.fixture
def receiver(tmp_path, monkeypatch):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append((self.path, self.headers.get("Authorization"), body))
            payload = json.dumps({
                "id": "routing-fixture", "object": "chat.completion", "created": 1,
                "model": body["model"],
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "ROUTE_OK"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("VIDEO_READER_API_KEY", "fixture-video")
    config = {
        "model": {"provider": "custom", "model": "selected-main", "supports_vision": True,
                  "base_url": endpoint + "/primary/v1", "api_key": "fixture-primary"},
        "terminal": {"cwd": str(tmp_path)},
        "auxiliary": {},
    }
    def save():
        (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    save()
    runtime = {"provider": "custom", "model": "selected-main",
               "base_url": endpoint + "/primary/v1", "api_key": "fixture-primary",
               "api_mode": "chat_completions"}
    aux.shutdown_cached_clients()
    try:
        with aux.scoped_runtime_main(runtime):
            yield config, save, received, endpoint, tmp_path
    finally:
        aux.shutdown_cached_clients()
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_default_text_and_image_auxiliary_use_selected_primary(receiver):
    _, _, received, _, _ = receiver
    for task in ("compression", "title_generation", "vision"):
        response = aux.call_llm(task=task, messages=[{"role": "user", "content": "summarize fixture"}])
        assert aux.extract_content_or_reasoning(response) == "ROUTE_OK"
    assert len(received) == 3
    assert all(path == "/primary/v1/chat/completions" and auth == "Bearer fixture-primary"
               and body["model"] == "selected-main" for path, auth, body in received)


def test_capable_primary_keeps_image_without_an_extra_reader_call(receiver):
    _, _, received, _, tmp_path = receiver
    from PIL import Image
    image = tmp_path / "native.png"
    Image.new("RGB", (8, 8), "blue").save(image)
    result = asyncio.run(vision._handle_vision_analyze({
        "image_url": str(image), "question": "Describe the fixture"}))
    assert isinstance(result, dict) and result["_multimodal"] is True
    assert any(part["type"] == "image_url" for part in result["content"])
    assert received == []  # The next primary turn consumes the native envelope.


def test_declared_video_capable_primary_receives_video_on_its_own_route(receiver):
    config, save, received, _, tmp_path = receiver
    config["providers"] = {"custom": {"models": {"selected-main": {
        "input_modalities": ["text", "image", "video"], "output_modalities": ["text"],
    }}}}
    save()
    clip = tmp_path / "primary.mp4"
    clip.write_bytes(b"fixture video payload")
    result = json.loads(asyncio.run(vision._handle_video_analyze({
        "video_url": str(clip), "question": "Describe the fixture"})))
    assert result["success"], result
    assert len(received) == 1
    path, auth, body = received[0]
    assert (path, auth, body["model"]) == (
        "/primary/v1/chat/completions", "Bearer fixture-primary", "selected-main")
    assert body["messages"][0]["content"][1]["type"] == "video_url"


def test_explicit_image_and_video_readers_have_independent_routes(receiver):
    config, save, received, endpoint, tmp_path = receiver
    config["auxiliary"] = {
        "vision": {"provider": "custom", "model": "image-reader",
                   "base_url": endpoint + "/image/v1", "api_key": "fixture-image"},
        "video": {"provider": "custom", "model": "video-reader",
                  "base_url": endpoint + "/video/v1", "key_env": "VIDEO_READER_API_KEY"},
    }
    save()
    # The primary is vision-capable, but the deliberately assigned reader must win.
    assert vision._should_use_native_vision_fast_path() is False
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
    image = tmp_path / "fixture.png"
    image.write_bytes(png)
    result = json.loads(asyncio.run(vision._handle_vision_analyze({
        "image_url": str(image), "question": "Describe the fixture"})))
    assert result["success"], result
    # Transport fixture only: these bytes are never claimed to be decoded video.
    clip = tmp_path / "fixture.mp4"
    clip.write_bytes(b"fixture video payload")
    result = json.loads(asyncio.run(vision._handle_video_analyze({
        "video_url": str(clip), "question": "Describe the fixture"})))
    assert result["success"], result
    assert [(p, a, b["model"]) for p, a, b in received] == [
        ("/image/v1/chat/completions", "Bearer fixture-image", "image-reader"),
        ("/video/v1/chat/completions", "Bearer fixture-video", "video-reader"),
    ]
    assert received[0][2]["messages"][0]["content"][1]["type"] == "image_url"
    assert received[1][2]["messages"][0]["content"][1]["type"] == "video_url"


def test_missing_specialist_key_stops_before_inference(receiver):
    config, save, received, endpoint, _ = receiver
    config["auxiliary"]["video"] = {
        "provider": "custom", "model": "video-reader", "base_url": endpoint + "/video/v1",
        "key_env": "MISSING_READER_API_KEY",
    }
    save()
    with pytest.raises(ValueError, match="credential is unavailable"):
        vision._video_route_kwargs(None)
    assert received == []
