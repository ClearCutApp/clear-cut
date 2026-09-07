from typing import Protocol


class SpeechTranscription(Protocol):
    def transcribe(self, audio: bytes, language: str) -> str: ...
