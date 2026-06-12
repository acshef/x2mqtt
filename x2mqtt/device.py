import typing as t

__all__ = ["Device"]


class Device(t.NamedTuple):
    identifiers: t.Sequence[str]
    name: str
    model: str
