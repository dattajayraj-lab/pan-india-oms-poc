"""Background jobs (single-process POC scheduler).

Each job is a plain function `job(db) -> None` registered by modules; the loop runs
them every 30 seconds. Jobs include CAS auto-escalation (Ch.5), code expiry and
pre-charging alerts (Cl. 11.4.4), and mock SCADA/weather feeds.
In production these move to a durable scheduler/worker (e.g. Celery beat / K8s CronJob).
"""
import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

log = logging.getLogger("oms.scheduler")
JOBS: list[tuple[str, Callable[[Session], None]]] = []
INTERVAL_SECONDS = 30


def register(name: str):
    def deco(fn):
        JOBS.append((name, fn))
        return fn

    return deco


def run_all_once() -> None:
    from app.db.session import SessionLocal, get_engine

    get_engine()
    for name, fn in JOBS:
        with SessionLocal() as db:
            try:
                fn(db)
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                log.exception("job %s failed", name)


async def run_forever() -> None:
    while True:
        await asyncio.sleep(INTERVAL_SECONDS)
        await asyncio.to_thread(run_all_once)
