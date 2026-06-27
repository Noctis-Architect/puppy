from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.config import AppConfig
from app.db.session import init_db
from app.logging_setup import setup_logging
from app.repositories.account_repo import AccountRepository
from app.telegram.auth import register_account


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="message-guard",
        description="Multi-user Telegram private message archive & delete alerts",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="Start monitoring service for all active accounts")
    sub.add_parser("add-user", help="Register a new Telegram account interactively")
    sub.add_parser("list-users", help="List registered accounts")

    deactivate = sub.add_parser("deactivate-user", help="Disable an account by id")
    deactivate.add_argument("account_id", type=int)

    activate = sub.add_parser("activate-user", help="Enable an account by id")
    activate.add_argument("account_id", type=int)

    return parser


async def cmd_add_user(config: AppConfig) -> None:
    setup_logging(config)
    factory = await init_db(config)
    async with factory() as db:
        account = await register_account(config, db)
        print(
            f"✅ کاربر ثبت شد: id={account.id} username={account.username or '-'} "
            f"session=session/{Path(account.session_path).name}.session"
        )


async def cmd_list_users(config: AppConfig) -> None:
    setup_logging(config)
    factory = await init_db(config)
    async with factory() as db:
        from sqlalchemy import select

        from app.db.models import Account

        result = await db.execute(select(Account).order_by(Account.id))
        accounts = list(result.scalars().all())

    if not accounts:
        print("هیچ کاربری ثبت نشده.")
        return

    print(f"{'ID':<5} {'Active':<8} {'Username':<16} {'Phone':<18} Name")
    print("-" * 75)
    for acc in accounts:
        username = f"@{acc.username}" if acc.username else "-"
        print(
            f"{acc.id:<5} {str(acc.is_active):<8} {username:<16} {acc.phone:<18} "
            f"{acc.display_name or '-'}"
        )


async def cmd_set_active(config: AppConfig, account_id: int, active: bool) -> None:
    setup_logging(config)
    factory = await init_db(config)
    async with factory() as db:
        repo = AccountRepository(db)
        account = await repo.get_by_id(account_id)
        if not account:
            print(f"Account {account_id} not found.")
            sys.exit(1)
        await repo.set_active(account_id, active)
        await db.commit()
        state = "فعال" if active else "غیرفعال"
        print(f"Account {account_id} {state} شد.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = AppConfig.load()

    if args.command == "run":
        from app.runtime import run_service

        asyncio.run(run_service(config))
    elif args.command == "add-user":
        asyncio.run(cmd_add_user(config))
    elif args.command == "list-users":
        asyncio.run(cmd_list_users(config))
    elif args.command == "deactivate-user":
        asyncio.run(cmd_set_active(config, args.account_id, False))
    elif args.command == "activate-user":
        asyncio.run(cmd_set_active(config, args.account_id, True))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
