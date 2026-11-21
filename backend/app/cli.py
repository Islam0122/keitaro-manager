"""Management commands.

    python -m app.cli create-user admin           # asks for the password
    python -m app.cli set-password admin
    echo "$PASS" | python -m app.cli create-user admin --password-stdin
"""
import argparse
import asyncio
import getpass
import sys

from pydantic import ValidationError

from app.schemas.auth import check_password_strength


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Password: ")
        if getpass.getpass("Repeat password: ") != password:
            raise SystemExit("Passwords do not match")
    try:
        return check_password_strength(password)
    except (ValueError, ValidationError) as exc:
        raise SystemExit(str(exc)) from exc


async def _run(args: argparse.Namespace) -> None:
    from app.db.session import SessionLocal, engine
    from app.services.auth_service import AuthService, normalize_username

    password = _read_password(args.password_stdin)
    try:
        async with SessionLocal() as session:
            service = AuthService(session)
            if args.command == "create-user":
                user = await service.create_user(args.username, password)
                print(f"User '{user.username}' created (id={user.id})")
            else:
                user = await service.users.get_by_username(normalize_username(args.username))
                if user is None:
                    raise SystemExit(f"User '{args.username}' not found")
                await service.set_password(user, password)
                print(f"Password of '{user.username}' updated")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("command", choices=["create-user", "set-password"])
    parser.add_argument("username")
    parser.add_argument("--password-stdin", action="store_true", help="read the password from stdin")
    args = parser.parse_args()
    try:
        asyncio.run(_run(args))
    except Exception as exc:
        message = getattr(exc, "message", None) or str(exc)
        raise SystemExit(f"Error: {message}") from exc


if __name__ == "__main__":
    main()
