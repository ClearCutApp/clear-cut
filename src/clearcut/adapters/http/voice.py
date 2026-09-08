"""Authorized, ephemeral audio upload returning an editable transcription."""

from typing import Any

from flask import Blueprint, request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors
from clearcut.application.voice_ports import SpeechTranscription
from clearcut.domain.voice import LANGUAGES, MAX_AUDIO_BYTES

TAG = "Voice questions"
TAG_DESCRIPTION = "Recording is transcribed, never automatically submitted as a question."
SCHEMAS: dict[str, Any] = {
    "Transcription": {
        "type": "object",
        "required": ["text", "language"],
        "properties": {"text": {"type": "string"}, "language": {"enum": sorted(LANGUAGES)}},
    }
}
PATHS: dict[str, Any] = {
    "/api/projects/{project_id}/transcriptions": {
        "post": {
            "tags": [TAG],
            "operationId": "transcribeQuestion",
            "summary": "Transcribe a recording for review",
            "parameters": [
                {"name": "project_id", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["audio", "language"],
                            "properties": {
                                "audio": {"type": "string", "format": "binary"},
                                "language": {"enum": sorted(LANGUAGES)},
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Editable transcript; audio not stored",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Transcription"}
                        }
                    },
                },
                "400": {
                    "description": (
                        "Empty, invalid or unsupported recording/language; maximum 60 seconds"
                    )
                },
                "413": {"description": "Audio exceeds 8 MiB"},
                "503": {"description": "Speech is not available in this environment"},
            },
        }
    }
}


def create_voice_blueprint(speech: SpeechTranscription | None) -> Blueprint:
    bp = Blueprint("clearcut_voice", __name__)

    @bp.errorhandler(413)
    def oversized(error: Any) -> ResponseReturnValue:
        return errors.error_response(413, "audio exceeds 8 MiB")

    @bp.post("/api/projects/<project_id>/transcriptions")
    def transcribe(project_id: str) -> ResponseReturnValue:
        if speech is None:
            return errors.error_response(
                503, "voice transcription is unavailable in this demo; type your question"
            )
        request.max_content_length = MAX_AUDIO_BYTES + 65536
        if request.content_length and request.content_length > MAX_AUDIO_BYTES + 65536:
            return errors.error_response(413, "audio exceeds 8 MiB")
        audio = request.files.get("audio")
        language = request.form.get("language", "")
        if audio is None or language not in LANGUAGES:
            return errors.error_response(400, "audio and a supported language are required")
        if audio.mimetype not in {
            "audio/webm",
            "audio/ogg",
            "audio/mp4",
            "audio/wav",
            "audio/x-wav",
        }:
            return errors.error_response(400, "record WebM/Opus, Ogg/Opus, MP4/AAC or WAV audio")
        data = audio.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            return errors.error_response(413, "audio exceeds 8 MiB")
        if not data:
            return errors.error_response(400, "recording is empty")
        return errors.run_use_case(
            lambda: {"text": speech.transcribe(data, language), "language": language}
        )

    return bp
