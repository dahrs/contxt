from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from pydantic import BaseModel

from app.config import settings
from app.logging import get_logger

log = get_logger(__name__)

_REQUEST_TIMEOUT_SECONDS = 15


class _WordOrderRow(BaseModel):
    name: str
    match: bool


class _PhonologyDiff(BaseModel):
    only_b: list[str]


class _WordOrderDiff(BaseModel):
    rows: list[_WordOrderRow]


class _MorphologyCategoryDiff(BaseModel):
    only_b: list[str]


class _MorphologyDiff(BaseModel):
    cases: _MorphologyCategoryDiff
    tenses: _MorphologyCategoryDiff
    moods: _MorphologyCategoryDiff


class _WritingSystemDiff(BaseModel):
    only_b: list[str]


class _VocabularyOriginDiff(BaseModel):
    shared: list[str]


class _Categories(BaseModel):
    phonology: _PhonologyDiff
    word_order: _WordOrderDiff
    morphology: _MorphologyDiff
    writing_system: _WritingSystemDiff
    vocabulary_origin: _VocabularyOriginDiff


class LanguageComparison(BaseModel):
    """A deliberately partial mirror of lingdiff's /compare response - only the fields
    summarize_for_teaching actually uses. Extra fields in the real response are ignored by
    pydantic by default, so this doesn't need to track lingdiff's full schema."""

    categories: _Categories
    label: str


def fetch_comparison(native_lang: str, target_lang: str) -> LanguageComparison | None:
    """Real computed typological-distance data for this pair, from the user's own lingdiff
    project, when configured and reachable. Returns None - never raises - if it isn't configured,
    the pair isn't recognized, or the request fails for any reason: this is enhancement, not a
    hard dependency - the generation prompt already produces native-aware content without it."""
    if not settings.lingdiff_api_url:
        log.debug(
            "lingdiff_api_url not configured - skipping real comparison data for %s->%s", native_lang, target_lang
        )
        return None

    query = urllib.parse.urlencode({"a": native_lang, "b": target_lang})
    url = f"{settings.lingdiff_api_url.rstrip('/')}/compare?{query}"
    try:
        with urllib.request.urlopen(url, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
        return LanguageComparison.model_validate(payload)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        log.warning("lingdiff comparison unavailable for %s->%s: %s", native_lang, target_lang, exc)
        return None


def summarize_for_teaching(comparison: LanguageComparison) -> str:
    """Compresses the rich /compare response into a compact prose block for a generation
    prompt - the things actually worth emphasizing, not a dump of the raw lists."""
    categories = comparison.categories
    lines = [f"Overall typological distance: {comparison.label}."]

    if categories.phonology.only_b:
        sounds = ", ".join(categories.phonology.only_b[:15])
        lines.append(f"Target-language sounds absent from the native phonology (priority phonetic focus): {sounds}.")

    mismatched_orders = [row.name for row in categories.word_order.rows if not row.match]
    if mismatched_orders:
        lines.append(f"Word-order features that differ (priority syntax focus): {', '.join(mismatched_orders)}.")

    grammar_gaps = (
        categories.morphology.cases.only_b + categories.morphology.tenses.only_b + categories.morphology.moods.only_b
    )
    if grammar_gaps:
        lines.append(
            f"Grammatical categories the target has that the native language lacks: {', '.join(grammar_gaps)}."
        )

    if categories.writing_system.only_b:
        lines.append(f"The target uses a different writing system: {', '.join(categories.writing_system.only_b)}.")

    if categories.vocabulary_origin.shared:
        lines.append(
            f"Both languages share loanwords from: {', '.join(categories.vocabulary_origin.shared)} - "
            "worth leaning on as potential cognates."
        )

    return " ".join(lines)
