"""严格加载Phase 7 TOML配置；缺失或非法配置在连接设备前失败。"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")


@dataclass(frozen=True)
class GatewayIdentity:
    gateway_id: str
    device_id: str


@dataclass(frozen=True)
class SerialConfig:
    port: str
    baud: int
    read_timeout_ms: int
    reconnect_initial_ms: int
    reconnect_max_ms: int


@dataclass(frozen=True)
class MqttConfig:
    host: str
    port: int
    keepalive_s: int
    client_id: str
    username: str
    password_env: str
    password: str | None
    qos_telemetry: int
    qos_state: int
    qos_command: int
    reconnect_initial_ms: int
    reconnect_max_ms: int


@dataclass(frozen=True)
class PublishConfig:
    motion_enabled: bool
    health_enabled: bool
    status_period_s: float
    gateway_metrics_period_s: float


@dataclass(frozen=True)
class LimitsConfig:
    telemetry_queue_capacity: int
    command_queue_capacity: int
    command_dedup_capacity: int
    command_dedup_ttl_s: int
    maximum_command_age_s: int


@dataclass(frozen=True)
class GatewayConfig:
    gateway: GatewayIdentity
    serial: SerialConfig
    mqtt: MqttConfig
    publish: PublishConfig
    limits: LimitsConfig


def _section(raw: dict, name: str, fields: set[str]) -> dict:
    value = raw.get(name)
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"[{name}] fields do not match required schema")
    return value


def load_gateway_config(path: str | Path) -> GatewayConfig:
    config_path = Path(path)
    if not config_path.is_file():
        raise ValueError(f"gateway config not found: {config_path}")
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    gateway = GatewayIdentity(**_section(raw, "gateway", {"gateway_id", "device_id"}))
    serial = SerialConfig(**_section(raw, "serial", {"port", "baud", "read_timeout_ms",
                                                       "reconnect_initial_ms", "reconnect_max_ms"}))
    mqtt_raw = _section(raw, "mqtt", {"host", "port", "keepalive_s", "client_id", "username",
                                       "password_env", "qos_telemetry", "qos_state", "qos_command",
                                       "reconnect_initial_ms", "reconnect_max_ms"})
    password_env = str(mqtt_raw["password_env"])
    mqtt = MqttConfig(**mqtt_raw, password=os.environ.get(password_env) if password_env else None)
    publish = PublishConfig(**_section(raw, "publish", {"motion_enabled", "health_enabled",
                                                          "status_period_s", "gateway_metrics_period_s"}))
    limits = LimitsConfig(**_section(raw, "limits", {"telemetry_queue_capacity", "command_queue_capacity",
                                                       "command_dedup_capacity", "command_dedup_ttl_s",
                                                       "maximum_command_age_s"}))
    for value in (gateway.gateway_id, gateway.device_id, mqtt.client_id):
        if not ID_PATTERN.fullmatch(value): raise ValueError(f"invalid stable identifier: {value}")
    if not serial.port or not mqtt.host: raise ValueError("serial port and MQTT host are required")
    if not (1200 <= serial.baud <= 3_000_000 and 1 <= mqtt.port <= 65535): raise ValueError("invalid port or baud")
    if not (1 <= serial.read_timeout_ms <= 5000 and 5 <= mqtt.keepalive_s <= 3600): raise ValueError("invalid timeout")
    if any(value not in (0, 1) for value in (mqtt.qos_telemetry, mqtt.qos_state, mqtt.qos_command)):
        raise ValueError("only MQTT QoS 0 or 1 is supported")
    if mqtt.username and not mqtt.password_env: raise ValueError("username requires password_env")
    for initial, maximum in ((serial.reconnect_initial_ms, serial.reconnect_max_ms),
                             (mqtt.reconnect_initial_ms, mqtt.reconnect_max_ms)):
        if initial < 100 or maximum < initial or maximum > 60000: raise ValueError("invalid reconnect bounds")
    if not (1 <= limits.telemetry_queue_capacity <= 4096 and 1 <= limits.command_queue_capacity <= 256 and
            1 <= limits.command_dedup_capacity <= 4096 and limits.command_dedup_ttl_s > 0 and
            limits.maximum_command_age_s > 0): raise ValueError("invalid limits")
    if publish.status_period_s <= 0 or publish.gateway_metrics_period_s <= 0: raise ValueError("invalid publish periods")
    return GatewayConfig(gateway, serial, mqtt, publish, limits)
