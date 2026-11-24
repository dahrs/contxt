from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.conversation.authenticity import verify_and_rephrase
from app.conversation.prompt import build_system_prompt
from app.conversation.session_plan import build_session_plan
from app.db.conversations import add_message, create_conversation, list_conversations, set_claude_session_id
from app.db.models import Conversation, Persona, User
from app.db.personas import get_persona
from app.db.users import get_interests
from app.llm.client import LLMClient
from app.persona.memory import sync_after_conversation
from app.persona.selection import shared_interest


def elapsed_since(timestamp: str | None) -> timedelta | None:
    if timestamp is None:
        return None
    return datetime.now(UTC) - datetime.fromisoformat(timestamp)


def start_conversation(
    llm: LLMClient, user: User, persona: Persona, kickoff_message: str, is_proactive: bool = False
) -> Conversation:
    """Shared by a user-initiated new conversation (chat_new), on-demand teacher access, and the
    daily proactive-outreach job - sync character-sheet/relationship state, build the session
    plan and system prompt, and generate the opening message. `kickoff_message` is what's sent as
    the first `generate()` turn (a plain greeting instruction for a user-initiated chat, or
    `build_proactive_kickoff_message()` for persona-initiated outreach)."""
    relationship_summary = sync_after_conversation(llm, user, persona)
    # sync_after_conversation may have just updated this persona's own character sheet (new/
    # dropped interest, routine change) - re-fetch so this conversation reflects that, not the
    # snapshot from before the sync ran.
    refreshed = get_persona(persona.id)
    if refreshed is not None:
        persona = refreshed

    prior_with_persona = [c for c in list_conversations(user.id) if c.persona_id == persona.id]
    time_since_last_contact = elapsed_since(prior_with_persona[0].started_at if prior_with_persona else None)

    plan = build_session_plan(user)
    interest = shared_interest(persona, get_interests(user.id))
    target_item_ids = [item.id for item in plan.due_items + plan.new_items]
    conversation = create_conversation(user.id, persona.id, plan.topic, target_item_ids, is_proactive=is_proactive)

    system_prompt = build_system_prompt(plan, persona, interest, relationship_summary, time_since_last_contact)
    reply_text, session_id = llm.generate(system_prompt, None, kickoff_message)
    focus_items = plan.due_items + plan.new_items + plan.learner_profile.chronic_issue_items
    reply_text = verify_and_rephrase(llm, persona, reply_text, focus_items)
    set_claude_session_id(conversation.id, session_id)
    add_message(conversation.id, "assistant", reply_text)

    return conversation
