"""MIT License.

Copyright (c) 2023 Ritik Ranjan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED typing. THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

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
    """Add a bot to the database."""
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
    "bot_id"  : f"{Fore.WHITE}Enter the bot's ID: {Fore.RESET}",
    "bot_name": f"{Fore.WHITE}Enter the bot's name: {Fore.RESET}",
    "prefix"  : f"{Fore.WHITE}Enter the bot's prefix: {Fore.RESET}",
    "status"  : f"{Fore.WHITE}Enter the bot's status: {Fore.RESET}",
    "activity": f"{Fore.WHITE}Enter the bot's activity: {Fore.RESET}",
    "media"   : f"{Fore.WHITE}Enter the bot's media: {Fore.RESET}",
    "owner_id": f"{Fore.WHITE}Enter the bot owner's ID: {Fore.RESET}",
    "cogs"    : f"{Fore.WHITE}Enter the bot's cogs (separated by a comma): {Fore.RESET}",
    "guild_id": f"{Fore.WHITE}Enter the bot's guild ID: {Fore.RESET}",
    "token"   : f"{Fore.WHITE}Enter the bot's token: {Fore.RESET}",
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
