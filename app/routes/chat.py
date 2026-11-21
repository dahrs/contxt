from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from app.auth.dependencies import require_user
from app.conversation.prompt import build_system_prompt, build_turn_reminder
from app.conversation.session_plan import build_session_plan
from app.conversation.signals import apply_outcomes, extract_outcomes
from app.db.conversations import (
    add_message,
    create_conversation,
    get_conversation,
    get_judged_item_ids,
    get_messages,
    list_conversations,
    set_claude_session_id,
)
from app.db.models import User
from app.db.personas import get_persona
from app.db.skills import get_skill_item
from app.db.users import get_interests
from app.llm import get_llm_client
from app.logging import get_logger
from app.persona.memory import sync_after_conversation
from app.persona.selection import select_persona, shared_interest

log = get_logger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


def _persona_name(persona_id: int) -> str:
    persona = get_persona(persona_id)
    return persona.name if persona is not None else "Unknown"


def _elapsed_since(timestamp: str | None) -> timedelta | None:
    if timestamp is None:
        return None
    return datetime.now(UTC) - datetime.fromisoformat(timestamp)


@router.get("/chat")
def chat_index(request: Request, user: User = Depends(require_user)) -> object:
    conversations = list_conversations(user.id)
    rows = [{"conversation": c, "persona_name": _persona_name(c.persona_id)} for c in conversations]
    return templates.TemplateResponse(request, "chat_index.html", {"rows": rows})


@router.post("/chat/new")
def chat_new(request: Request, user: User = Depends(require_user)) -> RedirectResponse:
    llm = get_llm_client()
    persona = select_persona(user)
    prior_with_persona = [c for c in list_conversations(user.id) if c.persona_id == persona.id]
    time_since_last_contact = _elapsed_since(prior_with_persona[0].started_at if prior_with_persona else None)

    relationship_summary = sync_after_conversation(llm, user, persona)
    # sync_after_conversation may have just updated this persona's own character sheet (new/
    # dropped interest, routine change) - re-fetch so this new conversation reflects that, per
    # the "replaces... every time a new conversation starts" requirement.
    refreshed_persona = get_persona(persona.id)
    if refreshed_persona is not None:
        persona = refreshed_persona

    plan = build_session_plan(user)
    interest = shared_interest(persona, get_interests(user.id))
    target_item_ids = [item.id for item in plan.due_items + plan.new_items]
    conversation = create_conversation(user.id, persona.id, plan.topic, target_item_ids)

    system_prompt = build_system_prompt(plan, persona, interest, relationship_summary, time_since_last_contact)
    reply_text, session_id = llm.generate(system_prompt, None, "(greet the learner and start the conversation)")
    set_claude_session_id(conversation.id, session_id)
    add_message(conversation.id, "assistant", reply_text)

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
    time_since_last_message = _elapsed_since(previous_messages[-1].created_at if previous_messages else None)

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
    add_message(conversation_id, "assistant", reply_text)

    return RedirectResponse(url=f"/chat/{conversation_id}", status_code=303)
