from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket

from sqlalchemy import Engine

from primestone.comic import library_service_from_settings
from primestone.config import Settings, get_settings
from primestone.db import create_db_engine
from primestone.editorial import editorial_service_from_settings
from primestone.jobs import ClaimedStep, PostgresJobQueue
from primestone.vision import vision_service_from_settings
from primestone_worker.editorial import register_editorial_handlers
from primestone_worker.handlers import HandlerRegistry, PermanentError, default_registry
from primestone_worker.library import register_library_handlers
from primestone_worker.vision import register_vision_handlers

logger = logging.getLogger("primestone.worker")


class Worker:
    def __init__(
        self,
        queue: PostgresJobQueue,
        handlers: HandlerRegistry,
        *,
        worker_id: str,
        retry_delay_seconds: float = 30.0,
    ) -> None:
        self._queue = queue
        self._handlers = handlers
        self.worker_id = worker_id
        self._retry_delay = retry_delay_seconds
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_once(self) -> bool:
        """Traite au plus une étape. Renvoie False si la file est vide."""
        step = await asyncio.to_thread(self._queue.claim, self.worker_id)
        if step is None:
            return False
        await self._execute(step)
        return True

    async def _execute(self, step: ClaimedStep) -> None:
        log = {"step_id": str(step.id), "step": step.name, "attempt": step.attempts}
        try:
            handler = self._handlers.get(step.name)
            result = await handler(step.payload)
        except PermanentError as exc:
            # Pas de nouvelle tentative : on épuise directement le compteur.
            exhausted = ClaimedStep(
                id=step.id,
                run_id=step.run_id,
                name=step.name,
                payload=step.payload,
                attempts=step.max_attempts,
                max_attempts=step.max_attempts,
            )
            await asyncio.to_thread(self._queue.fail, exhausted, f"permanent: {exc}")
            logger.error("étape en échec définitif", extra=log)
        except Exception as exc:
            status = await asyncio.to_thread(
                self._queue.fail,
                step,
                f"{type(exc).__name__}: {exc}",
                retry_delay_seconds=self._retry_delay,
            )
            logger.warning("étape en échec (%s)", status, extra=log)
        else:
            await asyncio.to_thread(self._queue.complete, step, result)
            logger.info("étape terminée", extra=log)

    async def run_forever(self, poll_interval: float, lease_seconds: int) -> None:
        await asyncio.to_thread(self._queue.recover_stale, lease_seconds)
        while not self._stop.is_set():
            worked = await self.run_once()
            if not worked:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=poll_interval)
                except TimeoutError:
                    await asyncio.to_thread(self._queue.recover_stale, lease_seconds)


def build_registry(settings: Settings, engine: Engine) -> HandlerRegistry:
    registry = default_registry()
    register_library_handlers(registry, library_service_from_settings(settings, engine))
    register_vision_handlers(registry, vision_service_from_settings(settings, engine))
    register_editorial_handlers(registry, editorial_service_from_settings(settings, engine))
    return registry


def main() -> None:
    settings: Settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    engine = create_db_engine(settings.database_url)
    worker = Worker(
        PostgresJobQueue(engine),
        build_registry(settings, engine),
        worker_id=f"{socket.gethostname()}:{os.getpid()}",
    )

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, worker.stop)
        await worker.run_forever(
            settings.worker_poll_interval_seconds, settings.worker_lease_seconds
        )

    try:
        asyncio.run(_run())
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
