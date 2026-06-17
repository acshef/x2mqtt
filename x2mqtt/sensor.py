from .const import *
from .entity import Entity

__all__ = ["Sensor"]


class Sensor[T, A: dict = dict](Entity[T, A]):
    domain = Domain.SENSOR
