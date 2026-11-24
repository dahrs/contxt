from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from app.auth.dependencies import require_user
from app.conversation.authenticity import verify_and_rephrase
from app.conversation.prompt import build_turn_reminder
from app.conversation.signals import apply_outcomes, extract_outcomes
from app.conversation.start import elapsed_since, start_conversation
from app.db.conversations import (
    add_message,
    get_conversation,
    get_judged_item_ids,
    get_messages,
    get_most_recent_conversation_with_persona,
    list_conversations,
    set_claude_session_id,
)
from app.db.models import Persona, User
from app.db.personas import get_beginner_teacher_persona, get_persona
from app.db.skills import get_skill_item
from app.llm import get_llm_client
from app.logging import get_logger
from app.persona.selection import is_free_now, select_persona

log = get_logger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


def _persona_name(persona_id: int) -> str:
    persona = get_persona(persona_id)
    return persona.name if persona is not None else "Unknown"


@router.get("/chat")
def chat_index(request: Request, user: User = Depends(require_user)) -> object:
    conversations = list_conversations(user.id)
    rows = [{"conversation": c, "persona_name": _persona_name(c.persona_id)} for c in conversations]

    # A heads-up before committing to a thread, not just an after-the-fact "sorry, busy" reply -
    # scoped to personas the user actually has a relationship with, not the whole roster.
    known_persona_ids = {c.persona_id for c in conversations}
    known_personas = [p for pid in known_persona_ids if (p := get_persona(pid)) is not None]
    available_now = sorted(p.name for p in known_personas if is_free_now(p))
    probably_busy = sorted(p.name for p in known_personas if not is_free_now(p))

    return templates.TemplateResponse(
        request, "chat_index.html", {"rows": rows, "available_now": available_now, "probably_busy": probably_busy}
    )


@router.post("/chat/new")
def chat_new(request: Request, user: User = Depends(require_user)) -> RedirectResponse:
    llm = get_llm_client()
    persona = select_persona(user)
    conversation = start_conversation(llm, user, persona, "(greet the learner and start the conversation)")
    return RedirectResponse(url=f"/chat/{conversation.id}", status_code=303)


@router.post("/chat/teacher")
def chat_teacher(request: Request, user: User = Depends(require_user)) -> RedirectResponse:
    """The beginner-teacher is a standing, on-demand reference, not a one-time onboarding step -
    continues the existing help thread if one exists, rather than starting a fresh one each time."""
    teacher: Persona | None = get_beginner_teacher_persona(user.target_lang)
    if teacher is None:
        return RedirectResponse(url="/chat", status_code=303)

    existing = get_most_recent_conversation_with_persona(user.id, teacher.id)
    if existing is not None:
        return RedirectResponse(url=f"/chat/{existing.id}", status_code=303)

    conversation = start_conversation(get_llm_client(), user, teacher, "(greet the learner and start the conversation)")
    return RedirectResponse(url=f"/chat/{conversation.id}", status_code=303)


@router.get("/chat/{conversation_id}")
def chat_view(request: Request, conversation_id: int, user: User = Depends(require_user)) -> object:
    conversation = get_conversation(conversation_id)
    if conversation is None or conversation.user_id != user.id:
        return RedirectResponse(url="/chat", status_code=303)
    messages = get_messages(conversation_id)
    persona_name = _persona_name(conversation.persona_id)
    return templates.TemplateResponse(
        request, "chat.html", {"conversation": conversation, "messages": messages, "persona_name": persona_name}
    )


@router.post("/chat/{conversation_id}/message")
def chat_send(
    request: Request, conversation_id: int, text: str = Form(...), user: User = Depends(require_user)
) -> RedirectResponse:
    conversation = get_conversation(conversation_id)
    if conversation is None or conversation.user_id != user.id:
        return RedirectResponse(url="/chat", status_code=303)

    previous_messages = get_messages(conversation_id)
    time_since_last_message = elapsed_since(previous_messages[-1].created_at if previous_messages else None)

    user_message = add_message(conversation_id, "user", text)

    already_judged = get_judged_item_ids(conversation_id)
    pending_item_ids = [item_id for item_id in conversation.target_item_ids if item_id not in already_judged]
    pending_items = [item for item_id in pending_item_ids if (item := get_skill_item(item_id)) is not None]
    outcomes = extract_outcomes(get_llm_client(), pending_items, text)
    apply_outcomes(user.id, user_message.id, outcomes)

    # The reminder is sent to the model only - add_message above already stored the clean text,
    # so the user's own transcript never shows it. See build_turn_reminder's docstring for why
    # this exists (the system prompt is fixed for the whole CLI session, so long conversations
    # need something fresher to keep the session's focus from fading with distance).
    persona = get_persona(conversation.persona_id)
    resolved_ids = {outcome.item_id for outcome in outcomes}
    still_pending_items = [item for item in pending_items if item.id not in resolved_ids]
    reminder = build_turn_reminder(persona, still_pending_items, time_since_last_message) if persona is not None else ""
    llm_message = f"{reminder}\n\n{text}" if reminder else text

    reply_text, session_id = get_llm_client().generate("", conversation.claude_session_id, llm_message)
    if conversation.claude_session_id is None:
        set_claude_session_id(conversation_id, session_id)
    if persona is not None:
        reply_text = verify_and_rephrase(get_llm_client(), persona, reply_text, still_pending_items)
    add_message(conversation_id, "assistant", reply_text)

    return RedirectResponse(url=f"/chat/{conversation_id}", status_code=303)
