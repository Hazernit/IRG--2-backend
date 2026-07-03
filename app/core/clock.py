from datetime import date, datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def today(self) -> date: ...

    def now(self) -> datetime: ...


class SystemClock:
    """UTC clock kept behind an interface so date-dependent rules stay testable."""

    def today(self) -> date:
        return self.now().date()

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


system_clock = SystemClock()

