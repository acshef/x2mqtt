import typing as t

from ..binary_sensor import BinarySensor
from ..const import *


class Running(BinarySensor[t.Any]):
    name = "Running"
    device_class = BinaryDeviceClass.RUNNING

    def get_binary_state(self, data):
        return not isinstance(data, Exception)
