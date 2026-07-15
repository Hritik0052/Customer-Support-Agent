import time
from contextlib import contextmanager


class Timer:
    """Elapsed wall-clock seconds for a block of work."""

    def __init__(self):
        self.elapsed = 0.0


@contextmanager
def timed():
    """
    with timed() as t:
        do_work()
    t.elapsed  # seconds, rounded to 2dp
    """
    timer = Timer()
    start = time.perf_counter()
    try:
        yield timer
    finally:
        timer.elapsed = round(time.perf_counter() - start, 2)


def truncate(text, limit=4000):
    """Clip overlong input before it reaches the model, to bound token cost."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"
