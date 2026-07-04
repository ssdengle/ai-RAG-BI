from apps.api.app.rag.processing import TextCleaner, TextNormalizer


def test_text_cleaner_removes_control_characters_and_normalizes_newlines() -> None:
    cleaner = TextCleaner()

    cleaned = cleaner.clean("Alpha\x00\r\nBeta\x07\rGamma")

    assert cleaned == "Alpha\nBeta\nGamma"


def test_text_normalizer_collapses_whitespace_and_blank_lines() -> None:
    normalizer = TextNormalizer()

    normalized = normalizer.normalize("Alpha   Beta\n\n\nGamma\t\tDelta")

    assert normalized == "Alpha Beta\n\nGamma Delta"
