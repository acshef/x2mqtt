import abc

from .const import *
from .entity import Entity

__all__ = ["BinarySensor"]


class BinarySensor[T, A: dict = dict](Entity[T, A], metaclass=abc.ABCMeta):
    domain = Domain.BINARY_SENSOR

    _payload_on = Payload.ON
    _payload_off = Payload.OFF

    def get_discovery_payload(self):
        data = super().get_discovery_payload()
        data.update(payload_on=self._payload_on, payload_off=self._payload_off)
        return data

    @abc.abstractmethod
    def get_binary_state(self, data: T) -> bool: ...

    def get_state(self, data: T):
        return self._payload_on if self.get_binary_state(data) else self._payload_off
