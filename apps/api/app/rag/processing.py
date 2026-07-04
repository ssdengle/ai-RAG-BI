from __future__ import annotations

import re
import unicodedata


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EXCESS_SPACES_RE = re.compile(r"[ \t]+")
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")


class TextCleaner:
    """Removes obvious extraction artifacts before normalization."""

    def clean(self, text: str) -> str:
        without_controls = _CONTROL_CHARS_RE.sub("", text)
        without_bom = without_controls.replace("\ufeff", "")
        normalized_newlines = without_bom.replace("\r\n", "\n").replace("\r", "\n")
        return normalized_newlines.strip()


class TextNormalizer:
    """Produces stable whitespace and Unicode for downstream chunking."""

    def normalize(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text)
        lines = [self._normalize_line(line) for line in normalized.split("\n")]
        collapsed = "\n".join(lines)
        collapsed = _EXCESS_BLANK_LINES_RE.sub("\n\n", collapsed)
        return collapsed.strip()

    @staticmethod
    def _normalize_line(line: str) -> str:
        trimmed = _EXCESS_SPACES_RE.sub(" ", line).strip()
        return trimmed
