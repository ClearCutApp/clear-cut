"""Voice questions are editable text before they become a submitted question."""


class InvalidRecording(ValueError):
    """The supplied recording cannot be transcribed."""


MAX_AUDIO_BYTES = 8 * 1024 * 1024
LANGUAGES = frozenset({"en-US", "es-419", "es-ES"})
