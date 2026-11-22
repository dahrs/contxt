from __future__ import annotations

from datetime import UTC, datetime

from app.config import settings
from app.conversation.prompt import build_proactive_kickoff_message
from app.conversation.start import elapsed_since, start_conversation
from app.db.connection import init_db
from app.db.conversations import list_conversations
from app.db.users import list_all_users, set_last_proactive_sent_at
from app.llm import get_llm_client
from app.logging import get_logger
from app.notifications.email import EmailNotConfiguredError, send_notification_email
from app.persona.selection import select_proactive_persona

log = get_logger(__name__)

_COOLDOWN_HOURS = settings.proactive_min_gap_hours


def _due_for_outreach(user_id: int, last_proactive_sent_at: str | None) -> bool:
    if not list_conversations(user_id):
        return False  # nothing to rekindle for a user who's never had a conversation yet
    gap = elapsed_since(last_proactive_sent_at)
    return gap is None or gap.total_seconds() / 3600 >= _COOLDOWN_HOURS


def _notify_by_email(email: str | None, persona_name: str) -> None:
    if email is None:
        return
    try:
        send_notification_email(
            email, f"{persona_name} sent you a message on contxt", f"{persona_name} just reached out - come say hi!"
        )
    except EmailNotConfiguredError:
        log.debug("skipping email notification - SMTP not configured")
    except Exception:
        log.exception("failed to send notification email to %s", email)


def main() -> int:
    init_db()
    now = datetime.now(UTC).isoformat()
    sent = 0
    for user in list_all_users():
        try:
            if not _due_for_outreach(user.id, user.last_proactive_sent_at):
                continue
            persona = select_proactive_persona(user)
            if persona is None:
                continue  # nobody in their top circle happens to be free this hour - expected

            llm = get_llm_client()
            start_conversation(llm, user, persona, build_proactive_kickoff_message(), is_proactive=True)
            set_last_proactive_sent_at(user.id, now)
            _notify_by_email(user.email, persona.name)
            sent += 1
            log.info("sent proactive message from persona %s to user %s", persona.id, user.id)
        except Exception:
            # One user's failure (e.g. a transient claude CLI error) must not abort the batch.
            log.exception("failed to process proactive outreach for user %s", user.id)

    print(f"Sent {sent} proactive message(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
