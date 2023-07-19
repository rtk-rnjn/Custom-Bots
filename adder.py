from __future__ import annotations

import os
from typing import Literal

from colorama import Fore, init, just_fix_windows_console

from utils import MONGO_CLIENT, Environment

if os.name == "nt":
    just_fix_windows_console()

init(autoreset=True)


def main(
    *,
    bot_id: int,
    bot_name: str,
    prefix: str,
    status: Literal["online", "idle", "dnd", "invisible"],
    activity: str,
    media: str,
    owner_id: int,
    cogs: list[str],
    guild_id: int,
    token: str,
) -> bool:
    payload = {}

    if not isinstance(bot_id, int):
        print(f"{Fore.RED}Error: bot_id must be an integer!")
        return False

    if status.lower() not in ("online", "idle", "dnd", "invisible"):
        print(f"{Fore.RED}Error: status must be one of the following: 'online', 'idle', 'dnd', 'invisible'!")
        return False

    if not isinstance(owner_id, int):
        print(f"{Fore.RED}Error: owner_id must be an integer!")
        return False

    if not isinstance(guild_id, int):
        print(f"{Fore.RED}Error: guild_id must be an integer!")
        return False

    if not isinstance(cogs, list):
        print(f"{Fore.RED}Error: cogs must be a list!")
        return False

    payload = {
        "id": bot_id,
        "name": bot_name,
        "prefix": prefix or "!",
        "status": status,
        "activity": activity,
        "media": media,
        "owner_id": owner_id,
        "cogs": cogs or ["~"],
        "guild_id": guild_id,
        "token": token,
    }

    collection = MONGO_CLIENT.customBots.mainConfigCollection
    try:
        collection.insert_one(payload)
    except KeyboardInterrupt:
        print(f"{Fore.RED}Exiting...")
        return False
    except Exception as e:
        print(f"{Fore.RED}Error: {e}")
        return False
    else:
        print(f"{Fore.GREEN}Successfully added {bot_name} to the database!")
        return True


# fmt: off
QUESTIONS = {
    "bot_id"  : f"{Fore.WHITE}Enter the bot's ID: {Fore.RESET}",  # noqa
    "bot_name": f"{Fore.WHITE}Enter the bot's name: {Fore.RESET}",  # noqa
    "prefix"  : f"{Fore.WHITE}Enter the bot's prefix: {Fore.RESET}",  # noqa
    "status"  : f"{Fore.WHITE}Enter the bot's status: {Fore.RESET}",  # noqa
    "activity": f"{Fore.WHITE}Enter the bot's activity: {Fore.RESET}",  # noqa
    "media"   : f"{Fore.WHITE}Enter the bot's media: {Fore.RESET}",  # noqa
    "owner_id": f"{Fore.WHITE}Enter the bot owner's ID: {Fore.RESET}",  # noqa
    "cogs"    : f"{Fore.WHITE}Enter the bot's cogs (separated by a comma): {Fore.RESET}",  # noqa
    "guild_id": f"{Fore.WHITE}Enter the bot's guild ID: {Fore.RESET}",  # noqa
    "token"   : f"{Fore.WHITE}Enter the bot's token: {Fore.RESET}",  # noqa
}
# fmt: on

if __name__ == "__main__":
    print(f"{Fore.GREEN}Welcome to the bot adder!")
    print(f"{Fore.GREEN}Please answer the following questions:")
    print(f"{Fore.GREEN}If you don't know the answer to a question, just press enter to skip it.")
    print()

    try:
        payload = {key: Environment.parse_entity(input(value), return_null=False) for key, value in QUESTIONS.items()}
    except KeyboardInterrupt:
        print(f"{Fore.RED}Exiting...")
        exit(1)

    print(f"{Fore.GREEN}Adding bot to the database...")

    main(**payload)  # type: ignore
