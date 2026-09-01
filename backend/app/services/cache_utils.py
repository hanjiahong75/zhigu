"""Tiny thread-safe in-memory TTL cache (no external deps)."""

import hashlib
import json
import threading
import time
from functools import wraps
from typing import Any, Callable

_lock = threading.Lock()
_store: dict = {}
_MAX_ENTRIES = 800


def _key(fn: Callable, args: tuple, kwargs: dict) -> str:
    try:
        payload = json.dumps(
            [fn.__module__, fn.__qualname__, list(args), kwargs],
            ensure_ascii=False, sort_keys=True, default=str,
        )
    except Exception:
        payload = f"{fn.__module__}.{fn.__qualname__}:{args}:{kwargs}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _prune(now: float) -> None:
    if len(_store) <= _MAX_ENTRIES:
        return
    expired = [k for k, (ts, _) in _store.items() if ts <= now]
    for k in expired:
        _store.pop(k, None)
    while len(_store) > _MAX_ENTRIES:
        oldest = min(_store, key=lambda k: _store[k][0])
        _store.pop(oldest, None)


def memo_ttl(seconds: int):
    """Cache a pure function's return by its (hashable) args for `seconds`."""
    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            k = _key(fn, args, kwargs)
            now = time.time()
            with _lock:
                hit = _store.get(k)
                if hit and hit[0] > now:
                    return hit[1]
            result = fn(*args, **kwargs)
            with _lock:
                _store[k] = (now + seconds, result)
                _prune(now)
            return result
        return wrapper
    return deco


def ttl_get(key: str, seconds: int, factory: Callable[[], Any]) -> Any:
    """Get a value by an explicit key, computing it via `factory` when stale."""
    now = time.time()
    with _lock:
        hit = _store.get(key)
        if hit and hit[0] > now:
            return hit[1]
    result = factory()
    with _lock:
        _store[key] = (now + seconds, result)
        _prune(now)
    return result
