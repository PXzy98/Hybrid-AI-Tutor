"""Account recovery from the command line (run on the application server, from backend/):

    python -m app.auth.cli create-instructor <username>
    python -m app.auth.cli set-password <username>        # also clears a lockout and ends all sessions
"""
import argparse
import getpass
import sys

from app.auth.service import AccountError
from app.core.config import get_settings
from app.core.services import build_services


def _ask_password() -> str:
    pw = getpass.getpass("New password: ")
    if pw != getpass.getpass("Repeat password: "):
        sys.exit("passwords do not match")
    return pw


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m app.auth.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("create-instructor").add_argument("username")
    sub.add_parser("set-password").add_argument("username")
    args = ap.parse_args(argv)

    accounts = build_services(get_settings()).accounts
    try:
        if args.cmd == "create-instructor":
            accounts.create_instructor(args.username, _ask_password(), must_change=False)
            print(f"instructor '{args.username}' created")
        else:
            account = accounts.get_by_username(args.username)
            accounts.set_password(account.id, _ask_password(), must_change=False)
            print(f"password set for '{account.username}'; all of its sessions were ended")
    except AccountError as e:
        sys.exit(f"error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
