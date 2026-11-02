"""PDF text writes must obey the same denial path as other file writes."""

import json
from pathlib import Path

import pytest

import tools.file_tools  # register the real handlers
from tools.registry import registry


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("content", ["# Maintenance report", "%PDF-1.4\nincomplete"])
def test_pdf_text_dispatch_never_creates_or_overwrites(tmp_path, monkeypatch, existing, content):
    home = tmp_path / "profile"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    destination = tmp_path / "report.pdf"
    original = b"%PDF-1.4\noriginal document\n%%EOF\n"
    if existing:
        destination.write_bytes(original)

    # Simulate the optional renderer being installed. A successful renderer
    # must not turn a denied file operation into a host-side write.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3]))
    import indra_tools.pdf
    rendered = []

    def render(source, output):
        rendered.append(output)
        Path(output).write_bytes(b"unapproved renderer output")

    monkeypatch.setattr(indra_tools.pdf, "render_pdf", render)
    result = json.loads(registry.dispatch("write_file", {
        "path": str(destination), "content": content,
    }, task_id="origo-pdf-denial"))

    assert result.get("error")
    assert not rendered
    if existing:
        assert destination.read_bytes() == original
    else:
        assert not destination.exists()
