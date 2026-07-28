from dataclasses import dataclass, field
from typing import Literal

AssomiCodeMsgScope = Literal['global', 'header_triple']


@dataclass(slots=True)
class CodeMsgSequence:
    """In-memory code_msg allocator with wrap-around and optional scope keys."""

    min_value: int
    max_value: int
    start_value: int
    scope: AssomiCodeMsgScope
    _current_by_scope: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if self.min_value > self.max_value:
            raise ValueError('min_value must be <= max_value')
        if not (self.min_value <= self.start_value <= self.max_value):
            raise ValueError('start_value must be within [min_value, max_value]')

    def peek(self, *, branch: str, system: str, name: str) -> int:
        key = self._scope_key(branch=branch, system=system, name=name)
        return self._current_by_scope.setdefault(key, self.start_value)

    def advance(self, *, branch: str, system: str, name: str) -> int:
        """Move to the next code after the current one; return the new current."""
        key = self._scope_key(branch=branch, system=system, name=name)
        current = self._current_by_scope.setdefault(key, self.start_value)
        nxt = self._next(current)
        self._current_by_scope[key] = nxt
        return nxt

    def mark_used_and_advance(self, *, branch: str, system: str, name: str) -> int:
        """After a successful ASSOMI call that consumed the peeked code."""
        return self.advance(branch=branch, system=system, name=name)

    def range_size(self) -> int:
        return self.max_value - self.min_value + 1

    def _next(self, current: int) -> int:
        if current >= self.max_value:
            return self.min_value
        return current + 1

    def _scope_key(self, *, branch: str, system: str, name: str) -> str:
        if self.scope == 'global':
            return 'global'
        return f'{branch}/{system}/{name}'
