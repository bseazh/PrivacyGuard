"""Request spans without request/response bodies, tokens or mapping values."""
from contextlib import contextmanager
import time


class Trace:
    def __init__(self, state, request_id):
        self.state, self.request_id = state, request_id

    @contextmanager
    def stage(self, name, details=None):
        details = dict(details or {})
        started = time.monotonic()
        span = self.state.trace_start(self.request_id, name, details)
        try:
            yield details
        except BaseException as exc:
            status = 'BLOCK' if hasattr(exc, 'code') else 'ERROR'
            # Store only stage outcome, never str(exc), which may contain original values.
            self.state.trace_finish(span, status, round((time.monotonic()-started)*1000), details)
            raise
        else:
            self.state.trace_finish(span, 'PASS', round((time.monotonic()-started)*1000), details)
