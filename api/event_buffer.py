import asyncio

from api.logger import get_logger

logger = get_logger(__name__)

FLUSH_INTERVAL_SECONDS = 1.5
MAX_BUFFER_SIZE = 500


class EventBuffer:
    """Accumulates normalized event row dicts and flushes them to the
    database in batches using a single multi-row INSERT."""

    def __init__(self) -> None:
        self._buffer: list[dict] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            f"Event buffer started (flush every {FLUSH_INTERVAL_SECONDS}s, "
            f"max batch {MAX_BUFFER_SIZE})"
        )

    async def stop(self) -> None:
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_now()
        logger.info("Event buffer stopped, remaining events flushed")

    async def add(self, row: dict) -> None:
        async with self._lock:
            self._buffer.append(row)
            should_flush = len(self._buffer) >= MAX_BUFFER_SIZE

        if should_flush:
            await self._flush_now()

    async def _flush_loop(self) -> None:
        while self._running:
            await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
            await self._flush_now()

    async def _flush_now(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer.clear()

        if not batch:
            return

        try:
            from api.database import AsyncSessionLocal
            from api.services.event_writer import bulk_insert_events

            async with AsyncSessionLocal() as session:
                await bulk_insert_events(session, batch)

            logger.debug(f"Flushed {len(batch)} buffered events to database")

        except Exception:
            logger.exception(f"Failed to flush {len(batch)} events, re-queuing")
            async with self._lock:
                self._buffer = batch + self._buffer


event_buffer = EventBuffer()
