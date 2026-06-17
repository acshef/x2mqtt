import abc
import functools
import hashlib
import json
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


class Entity[T, A: dict = dict](abc.ABC):
    DEFAULT_RETAIN = True
    DEFAULT_STATE_CLASS = StateClass.MEASUREMENT
    DEFAULT_ENABLED_BY_DEFAULT = True
    DEFAULT_INCLUDE_DATA_ERROR_ATTRIBUTE = False

    domain: Domain = None
    name: str = None

    device_class: str | None = None
    state_class: StateClass | None = StateClass.MEASUREMENT
    retain: bool = True
    unit_of_measurement: str | None = None
    icon: str | None = None
    enabled_by_default: bool = True
    include_data_error_attribute: bool = False

    def __init__(
        self,
        *,
        client: "Client",
        qos: int,
        topic_prefix: str,
        log: logging.Logger | None = None,
    ):
        if self.domain is None:
            raise ValueError("Entity must have a domain")

        if self.name is None:
            raise ValueError("Entity must have a name")

        if self.id == "availability":
            raise ValueError("Entity named 'availability' conflicts with shared availability topic")

        self.client = client
        self.qos = qos
        self.topic_prefix = topic_prefix
        self.log = log

    @functools.cached_property
    def state_topic(self) -> str:
        return f"{self.base_topic}/state"

    @functools.cached_property
    def attrs_topic(self) -> str:
        return f"{self.base_topic}/attributes"

    @functools.cached_property
    def id(self) -> str:
        return slugify(self.name)

    @property
    def base_topic(self) -> str:
        return f"{self.topic_prefix}/{self.id}"

    @functools.cached_property
    def unique_id(self) -> str:
        id_hash = hashlib.md5(self.base_topic.encode("utf-8"))
        return uuid.UUID(bytes=id_hash.digest()).hex

    @abc.abstractmethod
    def get_state(self, data: T | Exception) -> str: ...

    def get_attributes(self, data: T | Exception) -> A | None:
        return None

    def get_discovery_payload(self):
        data = {
            "device_class": self.device_class,
            "enabled_by_default": self.enabled_by_default,
            "icon": self.icon,
            "json_attributes_topic": self.attrs_topic,
            "name": self.name,
            "platform": self.domain,
            "state_class": self.state_class,
            "state_topic": self.state_topic,
            "unique_id": self.unique_id,
            "unit_of_measurement": self.unit_of_measurement,
        }

        return data

    def get_attributes_payload(self, data: T | Exception, state_error: str | None) -> str | None:
        data_error = data if isinstance(data, Exception) else None
        attrs_error = None

        try:
            attrs = dict(self.get_attributes(data) or {})
        except Exception as exc:
            attrs = {}
            attrs_error = self.pretty_print_exc(exc)

        if data_error and self.include_data_error_attribute:
            attrs["data_error"] = self.pretty_print_exc(data_error)
        if state_error:
            attrs["state_error"] = state_error
        if attrs_error:
            attrs["attrs_error"] = attrs_error

        return json.dumps(attrs) if attrs else None

    def publish_state(self, data: T | Exception):
        """
        Publish state to the state topic.
        Also publish attributes to the attributes topic.
        By default, the following attributes will be conditionally set:
        - "data_error", if the data itself is an Exception and self.include_data_error_attribute is True
        - "state_error", if the get_state method raised an Exception
        - "attrs_error", if the get_attributes method raised an Exception

        Additional attributes can be set by returning a dict (of generic type A) from the get_attributes(data) method.

        `data_error` is not included by default because sending new attribute payloads means a new forced state every interval.
        """

        state_error = None
        try:
            state = self.get_state(data)
        except Exception as exc:
            state_error = self.pretty_print_exc(exc)
        else:
            self._publish(self.state_topic, state)
            if self.log:
                self.log.getChild("state").info(
                    f"Publishing state {self.pretty_print_state(state)} to {self.name}"
                )
        attrs_payload = self.get_attributes_payload(data, state_error)
        if attrs_payload is not None:
            self._publish(self.attrs_topic, attrs_payload)
            if self.log:
                self.log.getChild("attrs").debug(
                    f"Publishing attrs {attrs_payload!r} to {self.name}"
                )

    def _publish(
        self,
        topic: str,
        payload: "PayloadType" = None,
        qos: int = None,
        retain: bool = None,
        properties: "Properties | None" = None,
    ) -> "MQTTMessageInfo":
        if retain is None:
            retain = self.retain
        if qos is None:
            qos = self.qos
        return self.client.publish(topic, payload, qos, retain, properties)

    @classmethod
    def pretty_print_state(cls, value: t.Any) -> str:
        if isinstance(value, enum.StrEnum):
            value = str(value)
        return repr(value)

    @classmethod
    def pretty_print_exc(cls, exc: Exception) -> str:
        return f"{type(exc).__qualname__}: {str(exc)}"

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
