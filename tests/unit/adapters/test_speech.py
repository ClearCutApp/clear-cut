from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from google.api_core.exceptions import InvalidArgument, PermissionDenied

from clearcut.adapters.gcp.speech import GoogleSpeechTranscription
from clearcut.adapters.http.voice import create_voice_blueprint
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.voice import InvalidRecording


def test_google_v2_uses_bounded_auto_decoding_and_returns_plain_transcript():
    client = Mock()
    client.recognize.return_value = SimpleNamespace(
        results=[
            SimpleNamespace(alternatives=[SimpleNamespace(transcript=" Hola ")]),
            SimpleNamespace(alternatives=[SimpleNamespace(transcript="mundo")]),
        ]
    )
    speech = GoogleSpeechTranscription(client, "test-project")
    assert speech.transcribe(b"recording", "es-419") == "Hola mundo"
    args = client.recognize.call_args.kwargs
    assert args["timeout"] == 45
    assert args["retry"] is None
    request = args["request"]
    assert request.content == b"recording"
    assert request.recognizer == "projects/test-project/locations/us-central1/recognizers/_"
    assert request.config.model == "chirp_2"
    assert list(request.config.language_codes) == ["es-419"]


@pytest.mark.parametrize(
    "provider,error",
    [
        (InvalidArgument("private bytes"), InvalidRecording),  # type: ignore[no-untyped-call]
        (PermissionDenied("private config"), SourceUnavailable),  # type: ignore[no-untyped-call]
    ],
)
def test_provider_errors_are_sanitized(provider, error):
    client = Mock()
    client.recognize.side_effect = provider
    with pytest.raises(error) as caught:
        GoogleSpeechTranscription(client, "project").transcribe(b"audio", "en-US")
    assert "private" not in str(caught.value)


def test_recording_route_returns_editable_transcript_without_submitting_question():
    speech = Mock()
    speech.transcribe.return_value = "Can we show this mural?"
    app = Flask(__name__)
    app.register_blueprint(create_voice_blueprint(speech))
    response = app.test_client().post(
        "/api/projects/p/transcriptions",
        data={"audio": (BytesIO(b"opus audio"), "voice.webm", "audio/webm"), "language": "en-US"},
    )
    assert response.status_code == 200
    assert response.json == {"text": "Can we show this mural?", "language": "en-US"}
    speech.transcribe.assert_called_once_with(b"opus audio", "en-US")


@pytest.mark.parametrize(
    "content,mime,language,status",
    [
        (b"", "audio/webm", "en-US", 400),
        (b"a", "video/mp4", "en-US", 400),
        (b"a", "audio/webm", "fr-FR", 400),
        (b"a" * (8 * 1024 * 1024 + 1), "audio/webm", "en-US", 413),
    ],
)
def test_recording_limits_fail_before_provider(content, mime, language, status):
    speech = Mock()
    app = Flask(__name__)
    app.register_blueprint(create_voice_blueprint(speech))
    response = app.test_client().post(
        "/api/projects/p/transcriptions",
        data={"audio": (BytesIO(content), "question", mime), "language": language},
    )
    assert response.status_code == status
    speech.transcribe.assert_not_called()


def test_demo_never_fabricates_transcription():
    app = Flask(__name__)
    app.register_blueprint(create_voice_blueprint(None))
    assert app.test_client().post("/api/projects/p/transcriptions").status_code == 503
