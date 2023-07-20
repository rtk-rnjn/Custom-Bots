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
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import logging

from colorama import Fore

DT_FMT = "%Y-%m-%d %H:%M:%S"

__all__ = ("CustomFormatter",)


class CustomFormatter(logging.Formatter):
    """Custom formatter for logging."""

    GRAY = f"{Fore.LIGHTBLACK_EX}"
    GREY = GRAY

    RED = f"{Fore.RED}"
    YELLOW = f"{Fore.YELLOW}"
    GREEN = f"{Fore.GREEN}"
    WHITE = f"{Fore.WHITE}"
    BLUE = f"{Fore.BLUE}"
    CYAN = f"{Fore.CYAN}"

    RESET = f"{Fore.RESET}"

    fmt = "{} %(asctime)s {} - {} %(name)s {} - {} %(levelname)s {} - {} %(message)s {} ({}%(filename)s/%(module)s.%(funcName)s{}:{}%(lineno)d{}){}"

    # fmt: off
    formats = {
        logging.DEBUG   : fmt.format(WHITE, WHITE, YELLOW, WHITE, GRAY  , WHITE, BLUE, WHITE, CYAN, YELLOW, GREEN, WHITE, RED),
        logging.INFO    : fmt.format(WHITE, WHITE, YELLOW, WHITE, GREEN , WHITE, BLUE, WHITE, CYAN, YELLOW, GREEN, WHITE, RED),
        logging.WARNING : fmt.format(WHITE, WHITE, YELLOW, WHITE, YELLOW, WHITE, BLUE, WHITE, CYAN, YELLOW, GREEN, WHITE, RED),
        logging.ERROR   : fmt.format(WHITE, WHITE, YELLOW, WHITE, RED   , WHITE, BLUE, WHITE, CYAN, YELLOW, GREEN, WHITE, RED),
        logging.CRITICAL: fmt.format(WHITE, WHITE, YELLOW, WHITE, RED   , WHITE, BLUE, WHITE, CYAN, YELLOW, GREEN, WHITE, RED),
    }
    # fmt: on

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record."""
        log_fmt = self.formats.get(record.levelno)
        formatter = logging.Formatter(log_fmt, DT_FMT)
        return formatter.format(record)
