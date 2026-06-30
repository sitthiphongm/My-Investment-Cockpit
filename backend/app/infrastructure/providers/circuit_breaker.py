"""Circuit breaker implementation for provider resilience."""

import time
from dataclasses import dataclass, field

from app.infrastructure.providers.base import CircuitState, ProviderStatus


@dataclass
class CircuitBreaker:
    """Circuit breaker that protects external provider calls.

    - CLOSED: requests pass through normally
    - OPEN: requests fail immediately (provider is down)
    - HALF_OPEN: one test request allowed to check recovery
    """

    provider_name: str
    failure_threshold: int = 5
    recovery_timeout: int = 300  # seconds

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _last_error: str | None = field(default=None, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def is_available(self) -> bool:
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        self._success_count += 1
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def record_failure(self, error: str = "") -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        self._last_error = error
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def get_status(self) -> ProviderStatus:
        total = self._success_count + self._failure_count
        return ProviderStatus(
            provider_name=self.provider_name,
            circuit_state=self.state,
            success_count=self._success_count,
            failure_count=self._failure_count,
            success_rate=self._success_count / total if total > 0 else 1.0,
            last_error=self._last_error,
        )
