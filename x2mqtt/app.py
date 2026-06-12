import abc
import argparse
import functools
import json
import logging
import os
import platform
import signal
import sys
import time
import typing as t

from paho.mqtt.client import Client
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from .const import *
from .device import Device
from .entity import Entity
from .origin import Origin
from .util import every, slugify

if t.TYPE_CHECKING:
    from .entity import Entity


__all__ = ["App"]

_is_exiting = False  # Global


class App[T](argparse.Namespace, metaclass=abc.ABCMeta):
    app_name = "x2mqtt"
    app_description = "A generic application built on the X2MQTT platform"
    env_var_prefix: str | None = None

    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_qos: int

    name: str
    ha_prefix: str
    interval: float

    verbose: int
    log_format: str

    topic_prefix: str
    client: Client
    device: Device
    origin: Origin

    def __call__(self) -> t.NoReturn:
        self.log.info("Starting %s v%s", self.app_name, self.get_version())
        self.set_device()
        self.set_origin()
        self.set_topic_prefix()

        self.set_client()

        entities = self.make_entities()

        self.client.connect(self.mqtt_host, self.mqtt_port)
        self.client.loop_start()

        signal.signal(signal.SIGINT, self.signal_handler)

        now = time.monotonic()
        while not self.client.is_connected():
            time.sleep(0.1)
        self.log.debug(f"Waited {time.monotonic() - now:.3f} sec to connect")

        self.setup_api()

        self.publish_discovery(entities)
        self.publish_states(entities)

        every(self.interval, self.publish_states, entities)

    def get_id(self) -> str:
        return platform.node()

    def set_topic_prefix(self) -> str:
        app_name = slugify(self.app_name.strip(" /")).strip(" /")
        name = slugify(self.name.strip(" /")).strip(" /")
        self.topic_prefix = f"{app_name}/{name}"

    def set_device(self):
        self.device = Device(
            identifiers=self.get_identifiers(),
            name=self.name,
            model=self.app_name,
        )

    def set_origin(self):
        self.origin = Origin(
            name=self.app_name,
            sw_version=self.get_version(),
        )

    def get_identifiers(self) -> list[str]:
        # Use dict to preserve order
        identifier = {}
        identifier[self.app_name] = None
        identifier[self.name] = None

        return list(identifier.keys())

    def make_entities(self) -> list["Entity[T]"]:
        from .entities import LastUpdatedAt, Running

        return [LastUpdatedAt.from_app(self), Running.from_app(self)]

    def set_client(self):
        client = Client(CallbackAPIVersion.VERSION2, self.client_id)
        client.username_pw_set(self.mqtt_username, self.mqtt_password)
        client.will_set(self.availability_topic, Payload.OFFLINE, qos=self.mqtt_qos, retain=True)
        client.on_connect = self.mqtt_on_connect
        client.on_connect_fail = self.mqtt_on_connect_fail
        client.on_disconnect = self.mqtt_on_disconnect

        self.client = client

    @functools.cached_property
    def client_id(self) -> str:
        app_name = slugify(self.app_name, "-").strip("-")
        name = slugify(self.name, "-").strip("-")
        return f"{app_name}-{name}"

    @functools.cached_property
    def availability_topic(self) -> str:
        return f"{self.topic_prefix}/availability"

    @functools.cached_property
    def log(self) -> logging.Logger:
        return logging.getLogger(self.app_name)

    def publish_discovery(self, entities: list["Entity[T]"]):
        self.log.info(
            f"Publishing discovery for {len(entities)} entit{'y' if len(entities) == 1 else 'ies'}"
        )

        # Publish device discovery: https://www.home-assistant.io/integrations/mqtt/#device-discovery-payload
        payload = {
            "availability_topic": self.availability_topic,
            "device": self.device._asdict(),
            "origin": self.origin._asdict(),
            "components": {entity.id: entity.get_discovery_payload() for entity in entities},
            "qos": self.mqtt_qos,
        }

        self.client.publish(
            f"{self.ha_prefix}/device/{self.topic_prefix}/config",
            json.dumps(payload),
            qos=self.mqtt_qos,
            retain=True,
        )

        self.log.info(f"Publishing availability for {self.name}")

        # Publish availability
        self._publish_availability(True)

    def _publish_availability(self, online: bool):
        value = Payload.ONLINE if online else Payload.OFFLINE
        self.client.publish(self.availability_topic, value, qos=self.mqtt_qos, retain=True)

    def publish_states(self, entities: list["Entity[T]"]):
        if not self.client.is_connected():
            return

        self._publish_availability(True)

        try:
            data = self.get_data()
        except Exception as exc:
            data = exc

        for entity in entities:
            entity.publish_state(data)

    def setup_api(self):
        return

    def get_data(self) -> T:
        return None

    def mqtt_on_connect(
        self,
        client: Client,
        userdata: t.Any,
        connect_flags: dict[str, t.Any],
        reason_code: ReasonCode,
        properties: Properties,
    ):
        self.log.info(f"Connected to MQTT broker: {reason_code.getName()} {properties.json()}")

    def mqtt_on_connect_fail(
        self,
        client: Client,
        userdata: t.Any,
    ):
        self.log.warning("Failed to connect to MQTT broker")

    def mqtt_on_disconnect(
        self,
        client: Client,
        userdata: t.Any,
        disconnect_flags: dict[str, t.Any],
        reason_code: ReasonCode,
        properties: Properties,
    ):
        self.log.warning(
            f"Disconnected from MQTT broker: {reason_code.getName()}, {properties.json()}"
        )

    def exit_gracefully(self, rc: int | None = None):
        if self.client.is_connected():
            self._publish_availability(False)
            self.client.loop_stop()
            self.client.disconnect()
        sys.exit(rc)

    def signal_handler(self, sig, frame):
        # Exit immediately upon receiving a second SIGINT
        global _is_exiting

        if _is_exiting:
            sys.exit(1)

        _is_exiting = True
        self.exit_gracefully()

    @classmethod
    def envname(cls, name: str, /) -> str:
        prefix = (cls.env_var_prefix or "").strip().rstrip("_")
        if prefix:
            return f"{prefix}_{name}"

        return name

    @classmethod
    def getenv(cls, name: str, /) -> str | None:
        return os.getenv(cls.envname(name))

    @classmethod
    def get_version(cls) -> str:
        return "UNKNOWN"

    @classmethod
    def create_parser(cls) -> argparse.ArgumentParser:

        parser = argparse.ArgumentParser(
            prog=cls.app_name,
            description=cls.app_description,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            add_help=False,
        )

        cls.setup_app_args(parser)
        cls.setup_mqtt_args(parser)
        cls.setup_general_args(parser)

        return parser

    @classmethod
    def setup_app_args(cls, parser: argparse.ArgumentParser):
        parser.add_argument(
            "--name",
            default=platform.node(),
            metavar="NAME",
            help="Device name. Defaults to the value of platform.node()",
        )

        parser.add_argument(
            "--ha-prefix",
            default=os.getenv(EnvVar.HA_PREFIX) or DEFAULT_HA_PREFIX,
            metavar="PREFIX",
            help=f"MQTT topic prefix for Home Assistant use. Defaults to the value of the {cls.envname(EnvVar.HA_PREFIX)} environment variable or {DEFAULT_HA_PREFIX!r} if that's not set",
        )

        interval_kwargs = {}
        try:
            interval_kwargs["default"] = int(cls.getenv(EnvVar.INTERVAL))
        except Exception:
            interval_kwargs["default"] = DEFAULT_INTERVAL
        parser.add_argument(
            "--interval",
            "-n",
            type=float,
            metavar="SEC",
            help=f"Interval (in seconds) for how often to update values. Defaults to the value of the {cls.envname(EnvVar.INTERVAL)} environment variable or {DEFAULT_INTERVAL!r} if that's not set",
            **interval_kwargs,
        )

    @classmethod
    def setup_mqtt_args(cls, parser: argparse.ArgumentParser):
        host_kwargs = {"default": cls.getenv(EnvVar.MQTT_HOST)}
        if not str(host_kwargs["default"] or "").strip():
            host_kwargs["required"] = True
        parser.add_argument(
            "--mqtt-host",
            metavar="HOST",
            help=f"MQTT Host. Defaults to the value of the {cls.envname(EnvVar.MQTT_HOST)} environment variable",
            **host_kwargs,
        )

        port_kwargs = {}
        try:
            port_kwargs["default"] = int(cls.getenv(EnvVar.MQTT_PORT))
        except Exception:
            port_kwargs["default"] = DEFAULT_MQTT_PORT
        parser.add_argument(
            "--mqtt-port",
            metavar="N",
            type=int,
            help=f"MQTT Port. Defaults to the value of the {cls.envname(EnvVar.MQTT_PORT)} environment variable or {DEFAULT_MQTT_PORT!r} if that's not set",
            **port_kwargs,
        )

        username_kwargs = {"default": os.getenv(EnvVar.MQTT_USERNAME)}
        if not str(username_kwargs["default"] or "").strip():
            username_kwargs["required"] = True
        parser.add_argument(
            "--mqtt-username",
            metavar="USERNAME",
            help=f"MQTT Username. Defaults to the value of the {cls.envname(EnvVar.MQTT_USERNAME)} environment variable",
            **username_kwargs,
        )

        password_kwargs = {"default": os.getenv(EnvVar.MQTT_PASSWORD)}
        if not str(password_kwargs["default"] or "").strip():
            password_kwargs["required"] = True
        parser.add_argument(
            "--mqtt-password",
            metavar="PASSWORD",
            help=f"MQTT Password. Defaults to the value of the {cls.envname(EnvVar.MQTT_PASSWORD)} environment variable",
            **password_kwargs,
        )

        qos_kwargs = {}
        try:
            qos_kwargs["default"] = int(cls.getenv(EnvVar.MQTT_QOS))
        except Exception:
            qos_kwargs["default"] = DEFAULT_MQTT_QOS
        parser.add_argument(
            "--mqtt-qos",
            metavar="N",
            type=int,
            help=f"MQTT QoS (Quality of Service) level. Defaults to the value of the {cls.envname(EnvVar.MQTT_QOS)} environment variable or {DEFAULT_MQTT_QOS!r} if that's not set",
            **qos_kwargs,
        )

    @classmethod
    def setup_general_args(cls, parser: argparse.ArgumentParser):
        parser.add_argument(
            "--help",
            "-h",
            "-?",
            action="help",
            help="Show this help message and exit",
        )
        parser.add_argument(
            "--version",
            "-V",
            action="version",
            version=f"%(prog)s v{cls.get_version()}",
            help="Show the program's version number and exit",
        )
        parser.add_argument(
            "--verbose",
            "-v",
            action="count",
            help="Verbosity. Pass once for error/warnings, twice for info, three times for debugging just this app, four times for debugging everything",
        )
        parser.add_argument(
            "--log-format",
            default=os.getenv(EnvVar.LOG_FORMAT) or DEFAULT_LOG_FORMAT,
            metavar="FMT",
            help=f"Percent-style format for Python logging. Defaults to the value of the {cls.envname(EnvVar.LOG_FORMAT)} environment variable or {DEFAULT_LOG_FORMAT.replace('%', '%%')!r} if that's not set",
        )

    @classmethod
    def create(cls, args=None, /) -> t.Self:
        parser = cls.create_parser()
        return parser.parse_args(args=args, namespace=cls())

    @classmethod
    def run(cls, args=None, /) -> t.NoReturn:
        app = cls.create(args)
        log = logging.getLogger(app.app_name)

        if app.verbose:
            if app.verbose >= 4:
                level = logging.DEBUG
            elif app.verbose >= 3:
                log.setLevel(logging.DEBUG)
                level = logging.INFO
            elif app.verbose >= 2:
                level = logging.INFO
            elif app.verbose >= 1:
                level = logging.WARNING

            logging.basicConfig(level=level, format=app.log_format)

        try:
            sys.exit(app())
        except Exception as exc:
            log.exception(exc)
            sys.exit(1)
