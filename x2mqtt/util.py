import time

from slugify import slugify as _slugify

from .const import *

__all__ = ["every", "slugify"]


def every(delay: float | int, task: callable, *args, **kwargs):
    next_time = time.monotonic() + delay
    while True:
        time.sleep(max(0, next_time - time.monotonic()))
        task(*args, **kwargs)
        # skip tasks if we are behind schedule:
        next_time += (time.monotonic() - next_time) // delay * delay + delay


def slugify(value: str, separator="_") -> str:
    """Slugify a value using underscores"""

    return _slugify(
        value,
        entities=False,
        decimal=False,
        hexadecimal=False,
        separator=separator,
        lowercase=True,
        allow_unicode=False,
    )
