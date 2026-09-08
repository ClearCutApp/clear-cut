from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from flask import Flask
from pypdf import PdfReader

from clearcut.adapters.demo.documents import MemoryProjectDocuments
from clearcut.adapters.demo.drafts import MemoryDraftStore, MemoryScreenplayContent
from clearcut.adapters.documents.screenplay_export import screenplay_fdx, screenplay_pdf
from clearcut.adapters.documents.screenplay_import import ScreenplayImporter
from clearcut.adapters.http.documents import create_documents_blueprint
from clearcut.adapters.http.drafts import create_drafts_blueprint
from clearcut.domain.document import InvalidDocument


def document() -> dict[str, Any]:
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "attrs": {"blockId": "b1", "sceneId": "s1", "kind": "scene-heading"},
                "content": [{"type": "text", "text": "INT. CAFÉ - DÍA"}],
            },
            {
                "type": "paragraph",
                "attrs": {"blockId": "b2", "sceneId": "s1", "kind": "dialogue"},
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '¿Quién pidió permiso? <img src="https://example.invalid/image">'
                            " & música."
                        ),
                        "marks": [{"type": "italic"}],
                    }
                ],
            },
        ],
    }


def test_fdx_roundtrip_preserves_spanish_text_and_screenplay_types():
    value, warnings = ScreenplayImporter().parse(
        "script.fdx", screenplay_fdx(document()), "uri", "file"
    )
    assert warnings == []
    assert [block["attrs"]["kind"] for block in value["content"]] == ["scene-heading", "dialogue"]
    assert (
        value["content"][1]["content"][0]["text"] == document()["content"][1]["content"][0]["text"]
    )


def test_pdf_escapes_markup_and_preserves_spanish_text():
    data = screenplay_pdf(document(), "Test screenplay", "revision-1")
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    assert "CAFÉ" in text
    assert "¿Quién pidió permiso?" in text
    assert "https://example.invalid/image" in text.replace("\n", "")
    assert "revision-1" in text


def test_long_dialogue_paginates_without_losing_end():
    value = document()
    value["content"][1]["content"][0]["text"] = "Diálogo de prueba. " * 1500 + "THE END"
    reader = PdfReader(BytesIO(screenplay_pdf(value, "Long screenplay", "revision-2")))
    assert len(reader.pages) > 2
    assert "THE END" in " ".join(reader.pages[-1].extract_text().split())


def test_docx_imports_paragraph_styles():
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:pPr><w:pStyle w:val="SceneHeading"/></w:pPr>'
            "<w:r><w:t>INT. ROOM - DAY</w:t></w:r></w:p>"
            '<w:p><w:pPr><w:pStyle w:val="Dialogue"/></w:pPr>'
            "<w:r><w:t>Hello.</w:t></w:r></w:p></w:body></w:document>",
        )
    value, warnings = ScreenplayImporter().parse("script.docx", data.getvalue(), "uri", "file")
    assert value["content"][1]["attrs"]["kind"] == "dialogue"
    assert warnings


def test_zip_expansion_and_xml_entities_are_rejected():
    data = BytesIO()
    with ZipFile(data, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"a" * (20 * 1024 * 1024 + 1))
    with pytest.raises(InvalidDocument, match="20 MiB"):
        ScreenplayImporter().parse("script.docx", data.getvalue(), "uri", "file")
    with pytest.raises(InvalidDocument):
        ScreenplayImporter().parse(
            "script.fdx",
            b'<!DOCTYPE FinalDraft [<!ENTITY x SYSTEM "file:///etc/passwd">]><FinalDraft><Content><Paragraph><Text>&x;</Text></Paragraph></Content></FinalDraft>',
            "uri",
            "file",
        )


def test_failed_import_retains_original_and_current_draft():
    documents, drafts, content = (
        MemoryProjectDocuments(),
        MemoryDraftStore(),
        MemoryScreenplayContent(),
    )
    app = Flask(__name__)
    app.register_blueprint(create_drafts_blueprint(drafts, content))
    app.register_blueprint(
        create_documents_blueprint(
            documents, drafts, content, ScreenplayImporter(), screenplay_pdf, screenplay_fdx
        )
    )
    client = app.test_client()
    root = "/api/projects/p"
    assert (
        client.put(
            root + "/draft", json={"expected_version": 0, "document": document()}
        ).status_code
        == 200
    )
    response = client.post(
        root + "/imports",
        data={"file": (BytesIO(b"invalid"), "script.fdx"), "expected_version": "1"},
    )
    assert response.status_code == 400
    assert client.get(root + "/draft").get_json()["document"] == document()
    originals = client.get(root + "/documents").get_json()["documents"]
    assert len(originals) == 1
    assert originals[0]["kind"] == "original"
    file_id = originals[0]["file_id"]
    assert client.get(root + "/documents/" + file_id).data == b"invalid"
    assert client.get("/api/projects/other/documents/" + file_id).status_code == 404


def test_successful_parse_cannot_overwrite_concurrent_edit_and_exports_fixed_revision():
    documents, drafts, content = (
        MemoryProjectDocuments(),
        MemoryDraftStore(),
        MemoryScreenplayContent(),
    )
    app = Flask(__name__)
    app.register_blueprint(create_drafts_blueprint(drafts, content))
    app.register_blueprint(
        create_documents_blueprint(
            documents, drafts, content, ScreenplayImporter(), screenplay_pdf, screenplay_fdx
        )
    )
    client = app.test_client()
    root = "/api/projects/p"
    client.put(root + "/draft", json={"expected_version": 0, "document": document()})
    revision = client.post(root + "/revisions", json={"expected_version": 1}).get_json()[
        "revision_id"
    ]
    response = client.post(
        root + "/imports",
        data={"file": (BytesIO(screenplay_fdx(document())), "script.fdx"), "expected_version": "0"},
    )
    assert response.status_code == 409
    assert client.get(root + "/draft").get_json()["version"] == 1
    exported = client.get(root + "/revisions/" + revision + "/exports/fdx")
    assert exported.status_code == 200
    assert exported.data == screenplay_fdx(document())


def test_pdf_import_produces_editable_blocks_and_review_warning():
    imported, warnings = ScreenplayImporter().parse(
        "screenplay.pdf", screenplay_pdf(document(), "Test", "revision-1"), "uri", "file"
    )
    assert imported["content"][0]["attrs"]["kind"] == "scene-heading"
    assert any("CAFÉ" in block["content"][0]["text"] for block in imported["content"])
    assert warnings


def test_revision_anchors_follow_actual_split_pdf_blocks_and_exact_text():
    from clearcut.adapters.documents.screenplay_export import screenplay_layout
    from clearcut.application.revision_scenes import revision_scenes

    value = document()
    value["content"][1]["content"][0]["text"] = "Diálogo extenso con autorización. " * 600
    pdf, pages = screenplay_layout(value, "Film", "revision-4")
    scenes, anchors = revision_scenes(value, pages)
    assert pages["b1"] == (1, 1)
    assert pages["b2"][1] > pages["b2"][0]
    assert pages["b2"][1] == len(PdfReader(BytesIO(pdf)).pages)
    assert anchors[0]["scene_id"] == "s1"
    block = anchors[0]["blocks"][1]
    assert block["block_id"] == "b2"
    assert (
        scenes[0].text[block["start"] : block["end"]] == value["content"][1]["content"][0]["text"]
    )
    assert scenes[0].page_end == pages["b2"][1]
