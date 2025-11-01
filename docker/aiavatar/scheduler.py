from datetime import datetime
from zoneinfo import ZoneInfo
import inspect
import logging
from typing import Callable, Union, Dict, Any
import anyio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)


class WaifuScheduler:
    def __init__(self, timezone: str, debug: bool = False):
        self.tz = ZoneInfo(timezone)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)
        self.debug = debug
        self._started = False

    def every(self, **interval_kwargs):
        """
        @mysched.every(seconds=..., minutes=..., hours=..., days=..., weeks=...,
                       id=..., max_instances=..., coalesce=..., misfire_grace_time=..., jitter=..., replace_existing=True)
        """
        def _decorator(func: Callable | None = None, /, **add_job_kwargs):
            # decorator with optional second-phrase options: @mysched.every(...)(id="x")
            if func is None:
                def inner(f: Callable):
                    return self._register_interval(f, interval_kwargs, add_job_kwargs)
                return inner
            return self._register_interval(func, interval_kwargs, add_job_kwargs)
        return _decorator

    def cron(self, expr: str, /, **add_job_kwargs):
        """
        @mysched.cron("*/5 * * * *", id=..., max_instances=..., ...)
        """
        trigger = CronTrigger.from_crontab(expr, timezone=self.tz)
        def _decorator(func: Callable):
            return self._register(func, trigger, add_job_kwargs)
        return _decorator

    def at(self, when: Union[str, datetime], /, **add_job_kwargs):
        """
        @mysched.at("2025-11-01T09:00:00", id=..., ...)
        """
        run_date = datetime.fromisoformat(when) if isinstance(when, str) else when
        if run_date.tzinfo is None:
            run_date = run_date.replace(tzinfo=self.tz)
        trigger = DateTrigger(run_date=run_date)
        def _decorator(func: Callable):
            return self._register(func, trigger, add_job_kwargs)
        return _decorator

    def _register(self, func: Callable, trigger, add_job_kwargs: Dict[str, Any]):
        # Parse args
        job_args  = tuple(add_job_kwargs.pop("args", ()) or ())
        job_kwargs = dict(add_job_kwargs.pop("kwargs", {}) or {})
        add_job_kwargs = {"replace_existing": True, **add_job_kwargs}

        # Add job
        self.scheduler.add_job(
            func=self._wrap_sync(func),
            trigger=trigger,
            args=job_args,
            kwargs=job_kwargs,
            **add_job_kwargs
        )

        return func

    def _register_interval(self, func: Callable, interval_kwargs: dict, add_job_kwargs: dict):
        trigger = IntervalTrigger(**interval_kwargs, timezone=self.tz)
        return self._register(func, trigger, add_job_kwargs)

    def _wrap_sync(self, func: Callable):
        if inspect.iscoroutinefunction(func):
            async def _runner(*a, **k):
                if self.debug:
                    logger.info(f"Run job (async): {func.__name__}, args={a}, kwargs={k}")
                return await func(*a, **k)
        else:
            async def _runner(*a, **k):
                if self.debug:
                    logger.info(f"Run job (sync): {func.__name__}, args={a}, kwargs={k}")
                return await anyio.to_thread.run_sync(lambda: func(*a, **k))
        return _runner

    def start(self):
        if self._started:
            return
        self.scheduler.start()
        self._started = True

    def shutdown(self):
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
