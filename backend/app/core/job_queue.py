"""In-process background queue for long-running work (segmentation).

Jobs run one at a time on a single background thread: inference is CPU- and
memory-heavy, so running two at once on a small instance would only make both slower
and risk running out of memory.

Known limitation: the queue lives in the web process. Jobs still waiting or running
when the process restarts are lost; `PatientService` detects such stale jobs and marks
them as failed. A dedicated worker with a persistent queue (Cloud Tasks, RQ, Celery)
removes this limitation.
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from app.core.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)


class JobQueue:
    def __init__(self, max_pending: int, inline: bool = False):
        """`inline=True` runs each job immediately in the caller's thread (tests)."""
        self._max_pending = max_pending
        self._inline = inline
        self._pending = 0
        self._lock = threading.Lock()
        self._executor = None if inline else ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="segmentation"
        )

    @property
    def pending(self) -> int:
        return self._pending

    def submit(self, job: Callable[[], None]) -> None:
        with self._lock:
            if self._pending >= self._max_pending:
                raise ServiceUnavailableError(
                    "The server is busy with other scans. Please try again in a few minutes."
                )
            self._pending += 1

        if self._inline:
            self._run(job)
        else:
            self._executor.submit(self._run, job)

    def _run(self, job: Callable[[], None]) -> None:
        try:
            job()
        except Exception:
            # Jobs record their own failures; this only guards the worker thread.
            logger.exception("Background job crashed")
        finally:
            with self._lock:
                self._pending -= 1
