import datetime
import typing as t

from ..const import *
from ..sensor import Sensor


class LastUpdatedAt(Sensor[t.Any]):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            name="Last Updated At",
            device_class=DeviceClass.TIMESTAMP,
            enabled_by_default=False,
            **kwargs,
        )

    def get_state(self, data):
        return datetime.datetime.now().astimezone().isoformat()
