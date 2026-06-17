import datetime
import typing as t

from ..const import *
from ..sensor import Sensor


class LastUpdatedAt(Sensor[t.Any]):
    name = "Last Updated At"
    device_class = DeviceClass.TIMESTAMP
    state_class = None
    enabled_by_default = False

    def get_state(self, data):
        return datetime.datetime.now().astimezone().isoformat()
