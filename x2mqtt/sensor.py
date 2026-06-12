from .const import *
from .entity import Entity

__all__ = ["Sensor"]


class Sensor[T](Entity[T]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, domain=Domain.SENSOR, **kwargs)
