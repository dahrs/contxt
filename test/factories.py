from __future__ import annotations

from app.db.models import Persona
from app.db.personas import create_persona


def make_persona(
    target_lang: str = "fra",
    name: str = "Test Persona",
    is_beginner_teacher: bool = False,
    interests: list[str] | None = None,
    free_hours: list[int] | None = None,
) -> Persona:
    """Minimal-content persona factory for tests that only care about identity/routing fields,
    not the prose content of psychological_profile/explanation_style/etc."""
    return create_persona(
        target_lang=target_lang,
        name=name,
        origin="N/A",
        age=30,
        background="N/A",
        physical_description="N/A",
        psychological_profile="N/A",
        social_habits="N/A",
        explanation_style="N/A",
        teaching_philosophy="N/A",
        correction_style="N/A",
        preferred_medium="N/A",
        vocabulary_strictness="N/A",
        cultural_depth="N/A",
        timezone="UTC",
        daily_routine="N/A",
        free_hours=free_hours if free_hours is not None else list(range(24)),
        interests=interests or [],
        is_beginner_teacher=is_beginner_teacher,
    )
