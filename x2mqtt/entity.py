import abc
import functools
import hashlib
import logging
import typing as t
import uuid

from .const import *
from .util import slugify

if t.TYPE_CHECKING:
    from paho.mqtt.client import Client, MQTTMessageInfo, PayloadType
    from paho.mqtt.properties import Properties

    from .app import App

__all__ = ["Entity"]


class Entity[T](abc.ABC):
    DEFAULT_RETAIN = True
    DEFAULT_STATE_CLASS = StateClass.MEASUREMENT

    domain: Domain
    name: str
    device_class: str | None
    state_class: str | None
    retain: bool
    unit_of_measurement: str | None
    icon: str | None
    enabled_by_default: bool

    def __init__(
        self,
        domain: Domain,
        name: str,
        *,
        client: "Client",
        qos: int,
        topic_prefix: str,
        log: logging.Logger | None = None,
        retain: bool | None = DEFAULT_RETAIN,
        device_class: str | None = None,
        state_class: StateClass | None = DEFAULT_STATE_CLASS,
        unit_of_measurement: str | None = None,
        icon: str | None = None,
        enabled_by_default: bool = True,
    ):
        self.domain = domain
        self.name = name

        if self.id == "availability":
            raise ValueError("Entity named 'availability' conflicts with shared availability topic")

        self.client = client
        self.qos = qos
        self.topic_prefix = topic_prefix
        self.log = log
        self.retain = retain
        self.device_class = device_class
        self.state_class = state_class
        self.unit_of_measurement = unit_of_measurement
        self.icon = icon
        self.enabled_by_default = enabled_by_default

    @functools.cached_property
    def id(self) -> str:
        return slugify(self.name)

    @functools.cached_property
    def base_topic(self) -> str:
        return f"{self.topic_prefix}/{self.id}"

    @functools.cached_property
    def state_topic(self) -> str:
        return f"{self.base_topic}/state"

    @functools.cached_property
    def unique_id(self) -> str:
        id_hash = hashlib.md5(self.id.encode("utf-8"))
        return uuid.UUID(bytes=id_hash.digest()).hex

    @abc.abstractmethod
    def get_state(self, data: T | Exception) -> str: ...

    def get_discovery_payload(self):
        data = {
            "device_class": self.device_class,
            "enabled_by_default": self.enabled_by_default,
            "name": self.name,
            "platform": self.domain,
            "state_class": self.state_class,
            "state_topic": self.state_topic,
            "unique_id": self.unique_id,
        }
        if self.unit_of_measurement:
            data["unit_of_measurement"] = self.unit_of_measurement
        if self.icon:
            data["icon"] = self.icon

        return data

    def _publish(
        self,
        topic: str,
        payload: "PayloadType" = None,
        retain: bool = None,
        properties: "Properties | None" = None,
    ) -> "MQTTMessageInfo":
        if retain is None:
            retain = self.retain
        return self.client.publish(topic, payload, self.qos, self.retain, properties)

    def publish_state(self, data: T | Exception):
        state = self.get_state(data)
        self._publish(self.state_topic, state)
        if self.log:
            self.log.getChild("state").info(
                f"Publishing state {self.pretty_print_state(state)} to {self.name}"
            )

    @classmethod
    def pretty_print_state(cls, value: t.Any) -> str:
        if isinstance(value, enum.StrEnum):
            value = str(value)
        return repr(value)

    @classmethod
    def from_app(cls, app: "App", *args, **kwargs) -> t.Self:
        return cls(
            *args,
            client=app.client,
            qos=app.mqtt_qos,
            topic_prefix=app.topic_prefix,
            log=app.log,
            **kwargs,
        )
