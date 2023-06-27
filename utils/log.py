import logging

from colorama import Fore

DT_FMT = "%Y-%m-%d %H:%M:%S"

__all__ = ("CustomFormatter",)


class CustomFormatter(logging.Formatter):
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
        logging.DEBUG    : fmt.format(WHITE, WHITE, YELLOW, WHITE, GRAY  , WHITE, BLUE, WHITE, CYAN, YELLOW, GREEN, WHITE, RED),
        logging.INFO     : fmt.format(WHITE, WHITE, YELLOW, WHITE, GREEN , WHITE, BLUE, WHITE, CYAN, YELLOW, GREEN, WHITE, RED),
        logging.WARNING  : fmt.format(WHITE, WHITE, YELLOW, WHITE, YELLOW, WHITE, BLUE, WHITE, CYAN, YELLOW, GREEN, WHITE, RED),
        logging.ERROR    : fmt.format(WHITE, WHITE, YELLOW, WHITE, RED   , WHITE, BLUE, WHITE, CYAN, YELLOW, GREEN, WHITE, RED),
        logging.CRITICAL : fmt.format(WHITE, WHITE, YELLOW, WHITE, RED   , WHITE, BLUE, WHITE, CYAN, YELLOW, GREEN, WHITE, RED),
    }
    # fmt: on

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.formats.get(record.levelno)
        formatter = logging.Formatter(log_fmt, DT_FMT)
        return formatter.format(record)
