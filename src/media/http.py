import hashlib
import json
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests
from requests.adapters import HTTPAdapter

MAX_WORKERS = 8


def response_cache_key(prefix: str, path: str, params: dict) -> str:
    """Short, whitespace-free cache key for an external API response."""
    raw = f'{path}?{json.dumps(params, sort_keys=True, separators=(",", ":"))}'
    return f'{prefix}:{hashlib.sha256(raw.encode()).hexdigest()}'


def build_session(pool_size: int = MAX_WORKERS) -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=1, pool_maxsize=pool_size)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def run_parallel(calls: Sequence[Callable[[], Any]], max_workers: int = MAX_WORKERS) -> list[Any]:
    """Run zero-arg callables concurrently, returning each result or raised exception in order.

    Callables must not touch the ORM: worker threads would open their own
    database connections outside the caller's transaction.
    """

    def capture(call):
        try:
            return call()
        except Exception as exc:
            return exc

    if len(calls) <= 1:
        return [capture(call) for call in calls]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(calls)), thread_name_prefix='media-http') as pool:
        return list(pool.map(capture, calls))
