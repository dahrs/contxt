from __future__ import annotations

import argparse
import sys

from app.auth.security import hash_password
from app.db.connection import init_db
from app.db.users import create_user
from app.logging import get_logger

log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a contxt account (invite-only, no self-serve signup).")
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("display_name")
    parser.add_argument("native_lang", help="e.g. eng")
    parser.add_argument("target_lang", help="e.g. fra")
    parser.add_argument(
        "--absolute-beginner",
        action="store_true",
        help="route their first-ever conversation to the dedicated beginner-teacher persona",
    )
    parser.add_argument("--email", default=None, help="optional, only used for proactive-message notifications")
    args = parser.parse_args()

    try:
        init_db()
        user = create_user(
            args.username,
            hash_password(args.password),
            args.display_name,
            args.native_lang,
            args.target_lang,
            is_absolute_beginner=args.absolute_beginner,
            email=args.email,
        )
    except Exception:
        log.exception("failed to create user %r", args.username)
        print(f"Failed to create user {args.username!r} - see logs/contxt.log", file=sys.stderr)
        return 1

    print(f"Created user {user.username!r} (id={user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
