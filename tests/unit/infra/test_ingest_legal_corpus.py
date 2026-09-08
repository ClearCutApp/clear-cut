from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from infra.fetch_legal_corpus import is_official
from infra.ingest_legal_corpus import ingest
from infra.legal_source_content import SourceRejected, download, extract


def manifest() -> dict[str, Any]:
    return {
        "countries": [
            {
                "documents": [
                    {
                        "id": "argentina-copyright",
                        "kind": "statute",
                        "jurisdiction": "argentina",
                        "subject": "copyright",
                        "title": "Law",
                        "as_of": "dated",
                        "url": "https://www.argentina.gob.ar/law",
                        "skip_pdf_pages": 0,
                    }
                ]
            }
        ]
    }


class Cloud:
    parent = "projects/p/locations/global/collections/default_collection/dataStores/d"
    bucket = SimpleNamespace(name="bucket")

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.submissions = 0
        self.done = False
        self.corrupt = False
        self.unknown = False

    def put(self, name, content, mime):
        assert self.objects.get(name, content) == content
        self.objects[name] = content
        return "gs://bucket/" + name

    def submit(self, uri):
        self.submissions += 1
        if self.unknown:
            raise RuntimeError("response lost")
        return self.parent + "/branches/0/operations/import1"

    def operation(self, name):
        return {"done": self.done, "response": {}}

    def document(self, identifier):
        import json

        batch = next(v for k, v in self.objects.items() if k.endswith(".jsonl"))
        record = json.loads(batch)
        if self.corrupt:
            record["structData"]["text_sha256"] = "incorrect"
        return record


def client() -> httpx.Client:
    def respond(request):
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text="<html><script>hidden</script><p>" + "Ley española. " * 100 + "</p></html>",
        )

    return httpx.Client(transport=httpx.MockTransport(respond))


def test_resume_keeps_originals_operation_and_requires_exact_readback(tmp_path):
    cloud = Cloud()
    with client() as http:
        first = ingest(manifest(), tmp_path, cloud, http)
        assert first["status"] == "importing"
        assert cloud.submissions == 1
        before = dict(cloud.objects)
        cloud.done = True
        cloud.corrupt = True
        with pytest.raises(SourceRejected, match="readback"):
            ingest(manifest(), tmp_path, cloud, http)
        cloud.corrupt = False
        result = ingest(manifest(), tmp_path, cloud, http)
        assert result["status"] == "imported_readback_verified"
        assert result["evaluation_status"] == "unverified"
        assert cloud.submissions == 1 and before == cloud.objects
        source = result["sources"]["argentina-copyright"]
        assert source["document"]["structData"]["original_sha256"] == source["original_sha256"]
        assert b"hidden" not in (tmp_path / "argentina-copyright.txt").read_bytes()
        (tmp_path / "argentina-copyright.txt").write_bytes(b"changed")
        with pytest.raises(SourceRejected, match="integrity"):
            ingest(manifest(), tmp_path, cloud, http)


def test_unknown_submission_never_blindly_resubmits(tmp_path):
    cloud = Cloud()
    cloud.unknown = True
    with client() as http:
        with pytest.raises(RuntimeError):
            ingest(manifest(), tmp_path, cloud, http)
        with pytest.raises(SourceRejected, match="outcome unknown"):
            ingest(manifest(), tmp_path, cloud, http)
    assert cloud.submissions == 1


def test_official_redirect_cannot_escape_or_use_userinfo():
    for url in (
        "https://evilwipo.int/a",
        "https://user@www.boe.es/a",
        "http://www.argentina.gob.ar/a",
        "https://www.boe.es:444/a",
    ):
        assert not is_official(url)
    assert is_official("https://www.boe.es/a")
    assert is_official("https://www.funcionpublica.gov.co/a")
    visited = []

    def respond(request):
        visited.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.example/law"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        with pytest.raises(SourceRejected, match="official HTTPS"):
            download(http, "https://www.boe.es/a")
    assert visited == ["https://www.boe.es/a"]


def test_missing_edition_and_login_pages_remain_gaps(tmp_path):
    body = ("<html>old privacy law " * 100 + "</html>").encode()
    with pytest.raises(SourceRejected, match="edition"):
        extract(body, "text/html", {"required_pattern": "2025"})
    with pytest.raises(SourceRejected, match="insufficient"):
        extract(b"<html>Please log in</html>", "text/html", {})
    cloud = Cloud()
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(403))) as http:
        receipt = ingest(manifest(), tmp_path, cloud, http)
    assert receipt["status"] == "coverage_gap"
    assert cloud.submissions == 0


def test_receipt_cannot_be_reused_for_another_target(tmp_path):
    cloud = Cloud()
    with client() as http:
        ingest(manifest(), tmp_path, cloud, http)
        cloud.parent += "-different"
        with pytest.raises(SourceRejected, match="another manifest"):
            ingest(manifest(), tmp_path, cloud, http)


def test_pdf_transformation_excludes_other_decision_and_rejects_mime():
    import io

    from reportlab.pdfgen.canvas import Canvas

    stream = io.BytesIO()
    canvas = Canvas(stream)
    canvas.drawString(40, 750, "DECISION 485 EXCLUDED")
    canvas.showPage()
    canvas.drawString(40, 750, "DECISION 486")
    for index in range(20):
        canvas.drawString(
            40, 720 - index * 20, "Article 134 protected distinctive marks and signs."
        )
    canvas.save()
    raw = stream.getvalue()
    text, transformation = extract(
        raw, "application/pdf", {"skip_pdf_pages": 1, "required_text": ["486"]}
    )
    assert b"486" in text and b"485" not in text
    assert transformation.endswith("skip-first-pages=1")
    with pytest.raises(SourceRejected, match="MIME"):
        extract(raw, "text/html", {})


def test_html_declared_encoding_preserves_accents():
    body = (
        '<html><meta charset="iso-8859-1"><p>' + "Artículo protección. " * 50 + "</p></html>"
    ).encode("latin-1")
    text, _ = extract(body, "text/html", {})
    assert "Artículo protección." in text.decode("utf-8")
