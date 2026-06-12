import typing as t

from ..binary_sensor import BinarySensor
from ..const import *


class Running(BinarySensor[t.Any]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="Running", device_class=BinaryDeviceClass.RUNNING, **kwargs)

    def get_binary_state(self, data):
        return not isinstance(data, Exception)
