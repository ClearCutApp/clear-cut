"""Bounded synchronous Speech V2 transcription; audio is never persisted here."""

from typing import Any

from google.api_core.exceptions import GoogleAPICallError, InvalidArgument, RetryError
from google.cloud.speech_v2.types import cloud_speech

from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.voice import LANGUAGES, MAX_AUDIO_BYTES, InvalidRecording


class GoogleSpeechTranscription:
    def __init__(
        self, client: Any, project: str, *, model: str = "chirp_2", timeout: float = 45
    ) -> None:
        self._client = client
        self._model, self._timeout = model, timeout
        self._recognizer = f"projects/{project}/locations/us-central1/recognizers/_"

    def transcribe(self, audio: bytes, language: str) -> str:
        if not audio or len(audio) > MAX_AUDIO_BYTES or language not in LANGUAGES:
            raise InvalidRecording("record up to 60 seconds in English or Spanish")
        request = cloud_speech.RecognizeRequest(
            recognizer=self._recognizer,
            config=cloud_speech.RecognitionConfig(
                auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
                language_codes=[language],
                model=self._model,
            ),
            content=audio,
        )
        try:
            response = self._client.recognize(request=request, retry=None, timeout=self._timeout)
        except InvalidArgument as exc:
            raise InvalidRecording(
                "recording could not be decoded; record up to 60 seconds and try again"
            ) from exc
        except (GoogleAPICallError, RetryError) as exc:
            raise SourceUnavailable("speech transcription is temporarily unavailable") from exc
        transcript = " ".join(
            result.alternatives[0].transcript.strip()
            for result in response.results
            if result.alternatives
        ).strip()
        if not transcript:
            raise InvalidRecording("no speech was recognized; try again or type your question")
        return transcript
