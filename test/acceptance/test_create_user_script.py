from __future__ import annotations

import sys

import pytest

from app.db.milestones import create_milestone
from app.db.skills import create_skill_item
from scripts.create_user import main
from test.factories import make_persona


def test__create_user_warns_when_no_content_exists_for_target_lang(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["create_user.py", "alice", "pw", "Alice", "eng", "fra"])

    exit_code = main()

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Note: no content yet for 'eng' -> 'fra'" in out
    assert "generate_personas.py fra" in out
    assert "generate_skill_items.py eng fra" in out


def test__create_user_does_not_warn_when_personas_and_items_exist(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    make_persona(target_lang="fra")
    milestone = create_milestone("Greetings", "Can greet someone", "A1")
    create_skill_item("vocab", "eng", "fra", "bonjour", milestone.id)
    monkeypatch.setattr(sys, "argv", ["create_user.py", "alice", "pw", "Alice", "eng", "fra"])

    main()

    assert "Note: no content yet" not in capsys.readouterr().out
