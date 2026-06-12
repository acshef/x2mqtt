import enum


class EnvVar(enum.StrEnum):
    MQTT_HOST = "MQTT_HOST"
    MQTT_PASSWORD = "MQTT_PASSWORD"
    MQTT_PORT = "MQTT_PORT"
    MQTT_QOS = "MQTT_QOS"
    MQTT_USERNAME = "MQTT_USERNAME"
    HA_PREFIX = "HA_PREFIX"
    INTERVAL = "INTERVAL"
    LOG_FORMAT = "LOG_FORMAT"


DEFAULT_MQTT_QOS = 0
DEFAULT_MQTT_PORT = 1883
DEFAULT_HA_PREFIX = "homeassistant"
DEFAULT_INTERVAL = 60.0
DEFAULT_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"


class BinaryDeviceClass(enum.StrEnum):
    RUNNING = "running"


class DeviceClass(enum.StrEnum):
    DATA_RATE = "data_rate"
    DURATION = "duration"
    TIMESTAMP = "timestamp"


class Domain(enum.StrEnum):
    BINARY_SENSOR = "binary_sensor"
    SENSOR = "sensor"


class Payload(enum.StrEnum):
    OFF = "off"
    OFFLINE = "offline"
    ON = "on"
    ONLINE = "online"


class StateClass(enum.StrEnum):
    """State class for sensors."""

    MEASUREMENT = "measurement"
    """The state represents a measurement in present time."""

    MEASUREMENT_ANGLE = "measurement_angle"
    """The state represents an angle measurement in present time.

    Currently only degrees are supported.
    """

    TOTAL = "total"
    """The state represents a total amount.

    For example: net energy consumption"""

    TOTAL_INCREASING = "total_increasing"
    """The state represents a monotonically increasing total.

    For example: an amount of consumed gas"""
