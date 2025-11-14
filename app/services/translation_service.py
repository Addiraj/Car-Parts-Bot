# Utility service wrapping googletrans to detect languages and translate text.


from __future__ import annotations
from functools import lru_cache
from typing import Optional
from googletrans import Translator


class TranslationService:
    """Lightweight wrapper to reuse a single Translator instance."""

    def __init__(self) -> None:
        self._translator = _get_translator()

    def detect_language(self, text: str) -> str:
        """Return ISO language code detected for the given text."""
        if not text:
            return "en"
        try:
            result = self._translator.detect(text)
            if result and getattr(result, "lang", None):
                return result.lang
        except Exception:
            pass
        return "en"

    def translate(self, text: str, target_language: str) -> str:
        """Translate text to the target language if needed."""
        if not text or not target_language:
            return text
        try:
            result = self._translator.translate(text, dest=target_language)
            if result and getattr(result, "text", None):
                return result.text
        except Exception:
            pass
        return text


@lru_cache(maxsize=1)
def _get_translator() -> Translator:
    return Translator()
