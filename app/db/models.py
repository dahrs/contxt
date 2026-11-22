from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SkillItemType = Literal["vocab", "grammar", "syntax", "phonetic", "register"]
MessageRole = Literal["user", "assistant"]
ItemOutcome = Literal["correct", "hesitant", "incorrect", "avoided"]


class User(BaseModel):
    id: int
    username: str
    password_hash: str
    display_name: str
    native_lang: str
    target_lang: str
    is_absolute_beginner: bool
    email: str | None
    last_proactive_sent_at: str | None
    created_at: str


class SkillItem(BaseModel):
    id: int
    type: SkillItemType
    target_lang: str
    content: str
    level: str
    category: str | None
    prerequisite_ids: list[int]


class UserItemState(BaseModel):
    user_id: int
    item_id: int
    fsrs_card_json: str
    reps: int
    lapses: int
    last_reviewed_at: str | None
    due_at: str


class Conversation(BaseModel):
    id: int
    user_id: int
    persona_id: int
    topic: str
    claude_session_id: str | None
    target_item_ids: list[int]
    is_proactive: bool
    started_at: str


class Message(BaseModel):
    id: int
    conversation_id: int
    role: MessageRole
    text: str
    created_at: str


class Persona(BaseModel):
    id: int
    target_lang: str
    name: str
    origin: str
    age: int
    background: str
    physical_description: str
    psychological_profile: str
    social_habits: str
    explanation_style: str
    teaching_philosophy: str
    correction_style: str
    preferred_medium: str
    vocabulary_strictness: str
    cultural_depth: str
    timezone: str
    daily_routine: str
    free_hours: list[int]
    is_beginner_teacher: bool
    interests: list[str]


class PersonaMemory(BaseModel):
    user_id: int
    persona_id: int
    summary: str
    last_summarized_message_id: int | None
    updated_at: str
