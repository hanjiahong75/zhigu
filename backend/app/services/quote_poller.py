"""Real-time quote polling service (M2).

Periodically fetches quotes for subscribed codes plus the watchlist and
publishes snapshots to SSE subscribers. Anti-overlap: a round is skipped if
the previous round is still in flight (borrowed from QuotePoller's
pollInFlight idea; Python reimplementation).
"""

import asyncio
import time
import uuid
from typing import Dict, List, Optional, Set, Tuple

from ..config import QUOTE_POLL_INTERVAL_SECONDS
from ..models.database import SessionLocal
from ..models.stock import WatchlistItem
from .stock_data import get_batch_quotes

_poller: Optional["QuotePoller"] = None


def get_quote_poller() -> "QuotePoller":
    """Return the process-wide quote poller singleton."""
    global _poller
    if _poller is None:
        _poller = QuotePoller()
    return _poller


class QuotePoller:
    """Background poller with an in-memory cache and pub/sub to SSE subscribers."""

    def __init__(self, interval_seconds: int = QUOTE_POLL_INTERVAL_SECONDS):
        self._default_interval = max(3, int(interval_seconds))
        self._interval = self._default_interval
        self._task: Optional[asyncio.Task] = None
        self._queues: Dict[str, asyncio.Queue] = {}
        self._intervals: Dict[str, int] = {}
        self._codes: Set[str] = set()
        self._cache: Dict[str, dict] = {}
        self._in_flight = False

    # -- lifecycle ------------------------------------------------------
    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    # -- subscription ---------------------------------------------------
    def add_subscriber(self, interval_seconds: int = 0) -> Tuple[str, asyncio.Queue]:
        sub_id = uuid.uuid4().hex
        self._queues[sub_id] = asyncio.Queue(maxsize=20)
        if interval_seconds >= 3:
            self._intervals[sub_id] = int(interval_seconds)
            self._recompute_interval()
        return sub_id, self._queues[sub_id]

    def remove_subscriber(self, sub_id: str) -> None:
        self._queues.pop(sub_id, None)
        self._intervals.pop(sub_id, None)
        self._recompute_interval()

    def register_codes(self, codes: List[str]) -> None:
        self._codes.update(codes)

    def unregister_codes(self, codes: List[str]) -> None:
        for c in codes:
            self._codes.discard(c)

    def set_interval(self, seconds: int) -> None:
        self._interval = max(3, min(60, int(seconds)))

    def _recompute_interval(self) -> None:
        values = [self._default_interval] + list(self._intervals.values())
        self._interval = max(3, min(values))

    # -- cache / snapshot ------------------------------------------------
    def get_cached_quotes(self, codes: Optional[List[str]] = None) -> Dict[str, dict]:
        if codes is None:
            return dict(self._cache)
        wanted = set(codes)
        return {c: q for c, q in self._cache.items() if c in wanted}

    def snapshot(self, codes: Optional[List[str]] = None) -> dict:
        quotes = self.get_cached_quotes(codes)
        return {"type": "quotes", "ts": int(time.time()), "quotes": list(quotes.values())}

    # -- internals -------------------------------------------------------
    async def _poll_loop(self) -> None:
        while True:
            try:
                await self._poll_once()
            except Exception:
                pass  # never let the loop die
            await asyncio.sleep(self._interval)

    async def _poll_once(self) -> None:
        if self._in_flight:
            return  # anti-overlap: skip round if previous still running
        self._in_flight = True
        try:
            codes: Set[str] = set(self._codes)
            codes.update(self._load_watchlist_codes())
            if not codes:
                return
            quotes = await asyncio.to_thread(get_batch_quotes, list(codes))
            if quotes:
                self._cache.update(quotes)
                self._publish(self.snapshot())
        finally:
            self._in_flight = False

    def _load_watchlist_codes(self) -> List[str]:
        try:
            db = SessionLocal()
            try:
                rows = db.query(WatchlistItem.code).all()
                return [r[0] for r in rows]
            finally:
                db.close()
        except Exception:
            return []

    def _publish(self, message: dict) -> None:
        if not self._queues:
            return
        for q in list(self._queues.values()):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()  # drop oldest
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(message)
                except asyncio.QueueFull:
                    pass
