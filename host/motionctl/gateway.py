"""单DeviceClient串口到MQTT网关，含有界命令队列、去重和安全退出。"""

from __future__ import annotations

import queue
import random
import signal
import threading
import time
from collections import OrderedDict
from dataclasses import asdict
from typing import Any, Callable

from . import __version__, commands
from .commands import (RuntimeConfig, decode_actuator_status, decode_device_info,
                       decode_health, decode_motion, decode_status)
from .device import DeviceClient
from .gateway_config import GatewayConfig
from .gateway_metrics import GatewayMetrics
from .models import stable_dict
from .mqtt_client import MqttClient
from .mqtt_models import (MqttCommand, SIDE_EFFECT_COMMANDS, json_bytes,
                          response_payload, unix_ms, utc_iso)
from .mqtt_topics import SCHEMA_VERSION, TopicSet
from .transport import SerialTransport


COMMAND_IDS = {"ping": commands.PING, "get_device_info": commands.GET_DEVICE_INFO,
               "get_status": commands.GET_STATUS, "get_config": commands.GET_CONFIG,
               "set_config": commands.SET_CONFIG, "start_calibration": commands.START_CALIBRATION,
               "set_stream_state": commands.SET_STREAM_STATE,
               "get_latest_motion": commands.GET_LATEST_MOTION,
               "actuator_status": commands.ACTUATOR_GET_STATUS,
               "actuator_arm": commands.ACTUATOR_ARM,
               "actuator_disarm": commands.ACTUATOR_DISARM,
               "actuator_center": commands.ACTUATOR_CENTER,
               "actuator_set_target": commands.ACTUATOR_SET_TARGET,
               "actuator_estop": commands.ACTUATOR_ESTOP}


class CommandResultCache:
    def __init__(self, capacity: int, ttl_s: int) -> None:
        self.capacity, self.ttl_s = capacity, ttl_s
        self._items: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()

    def purge(self, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        while self._items and current - next(iter(self._items.values()))[0] > self.ttl_s:
            self._items.popitem(last=False)

    def get(self, request_id: str) -> dict[str, Any] | None:
        self.purge()
        item = self._items.get(request_id)
        if item is None: return None
        self._items.move_to_end(request_id)
        return item[1]

    def put(self, request_id: str, response: dict[str, Any]) -> None:
        self.purge()
        self._items[request_id] = (time.monotonic(), response)
        self._items.move_to_end(request_id)
        while len(self._items) > self.capacity: self._items.popitem(last=False)

    def __len__(self) -> int: return len(self._items)


class ReconnectBackoff:
    """Bounded exponential reconnect delay with a small positive jitter."""

    def __init__(self, initial_ms: int, maximum_ms: int, jitter_ratio: float = 0.1) -> None:
        self.initial_s = initial_ms / 1000.0
        self.maximum_s = maximum_ms / 1000.0
        self.jitter_ratio = jitter_ratio
        self._delay_s = self.initial_s

    def next_delay(self) -> float:
        base = self._delay_s
        self._delay_s = min(self.maximum_s, max(self.initial_s, base * 2.0))
        return min(self.maximum_s, base + random.uniform(0.0, base * self.jitter_ratio))

    def reset(self) -> None:
        self._delay_s = self.initial_s


class Gateway:
    def __init__(self, config: GatewayConfig, *, mqtt_factory=MqttClient,
                 transport_factory: Callable[..., Any] = SerialTransport) -> None:
        self.config = config
        self.topics = TopicSet(config.gateway.device_id, config.gateway.gateway_id)
        self.rules = self.topics.rules(config.mqtt.qos_telemetry, config.mqtt.qos_state,
                                       config.mqtt.qos_command)
        self.metrics = GatewayMetrics()
        self.command_queue: queue.Queue[tuple[bytes, bool]] = queue.Queue(config.limits.command_queue_capacity)
        self.cache = CommandResultCache(config.limits.command_dedup_capacity,
                                        config.limits.command_dedup_ttl_s)
        self._transport_factory = transport_factory
        self._device: DeviceClient | None = None
        self._stop = threading.Event()
        self._last_error: str | None = None
        self._info = None
        self._status = None
        self._config = None
        self._actuator_status = None
        self._last_motion_sequence: int | None = None
        self._original_stream: bool | None = None
        self._mqtt = mqtt_factory(config.mqtt,
                                  will_topic=self.topics.gateway_availability,
                                  will_payload=b"offline", on_message=self._on_mqtt_message)
        self._mqtt.add_subscription(self.topics.command, config.mqtt.qos_command)

    def _publish(self, rule_name: str, value: Any) -> bool:
        rule = self.rules[rule_name]
        payload = value if isinstance(value, (str, bytes)) else json_bytes(value)
        ok = self._mqtt.publish(rule.topic, payload, qos=rule.qos, retain=rule.retain)
        if ok: self.metrics.increment("mqtt_messages_published")
        return ok

    def _on_mqtt_message(self, topic: str, payload: bytes, retained: bool) -> None:
        if topic != self.topics.command: return
        if not payload: return
        try:
            self.command_queue.put_nowait((payload, retained))
            self.metrics.high_water("command_queue_high_water", self.command_queue.qsize())
        except queue.Full:
            self.metrics.increment("command_errors")
            self._last_error = "command queue full"

    def _connect_device(self) -> None:
        transport = self._transport_factory(self.config.serial.port, self.config.serial.baud,
                                            timeout=self.config.serial.read_timeout_ms / 1000.0)
        self._device = DeviceClient(transport, timeout=1.0, retries=3)
        self._device.flush_input()
        self._device.request(commands.PING)
        self._info = decode_device_info(self._device.request(commands.GET_DEVICE_INFO))
        self._config = RuntimeConfig.unpack(self._device.request(commands.GET_CONFIG))
        self._status = decode_status(self._device.request(commands.GET_STATUS),
                                     stream_enabled=self._config.telemetry_enabled)
        self._actuator_status = decode_actuator_status(
            self._device.request(commands.ACTUATOR_GET_STATUS))
        if self._original_stream is None: self._original_stream = self._config.telemetry_enabled
        if not self._config.telemetry_enabled:
            self._device.request(commands.SET_STREAM_STATE, b"\1", retry=False)
            self._config = RuntimeConfig.unpack(self._device.request(commands.GET_CONFIG))
        self._device.flush_input()

    def _meta(self) -> dict:
        return {"schema_version": SCHEMA_VERSION, "device_id": self.config.gateway.device_id,
                "device_name": self._info.device_name if self._info else None,
                "firmware_version": self._info.firmware_version if self._info else None,
                "protocol_version": self._info.protocol_version if self._info else None,
                "gateway_version": __version__, "mcu": self._info.mcu_model if self._info else None,
                "imu": self._info.imu_model if self._info else None,
                "capabilities": self._info.capabilities if self._info else None}

    def _state(self) -> dict:
        return {"schema_version": SCHEMA_VERSION, "device_id": self.config.gateway.device_id,
                "app_state": self._status.app_state if self._status else "OFFLINE",
                "sensor_online": bool(self._status and self._status.sensor_state == "RUNNING"),
                "calibrated": self._status.calibrated if self._status else None,
                "stream_enabled": self._config.telemetry_enabled if self._config else None,
                "uptime_ms": self._status.uptime_ms if self._status else None,
                "last_motion_sequence": self._last_motion_sequence,
                "actuator": stable_dict(self._actuator_status) if self._actuator_status else None,
                "error_counts": self._status.protocol_errors if self._status else None,
                "received_at": utc_iso(), "published_at": utc_iso()}

    def _publish_online_snapshot(self) -> None:
        self._publish("gateway_availability", "online")
        self._publish("device_availability", "online" if self._device else "offline")
        if self._device:
            self._publish("meta", self._meta())
            self._publish("state", self._state())
        self._publish("gateway_state", self.status())

    def _gateway_metrics(self) -> dict:
        return {"schema_version": SCHEMA_VERSION,
                "gateway_id": self.config.gateway.gateway_id,
                "device_id": self.config.gateway.device_id,
                **self.metrics.snapshot(), "published_at": utc_iso()}

    def _publish_motion(self, frame) -> None:
        received_unix = unix_ms(); received_ns = time.monotonic_ns()
        sample = decode_motion(frame.payload, received_ns)
        self._last_motion_sequence = sample.sample_sequence
        value = {"schema_version": SCHEMA_VERSION, "device_id": self.config.gateway.device_id,
                 "device_timestamp_ms": sample.device_timestamp_ms, "sequence": sample.sample_sequence,
                 "roll_deg": sample.roll_deg, "pitch_deg": sample.pitch_deg,
                 "accel_mg": {"x": sample.ax_mg, "y": sample.ay_mg, "z": sample.az_mg},
                 "gyro_mdps": {"x": sample.gx_mdps, "y": sample.gy_mdps, "z": sample.gz_mdps},
                 "calibrated": sample.calibrated,
                 "app_state": self._status.app_state if self._status else None,
                 "gateway_received_unix_ms": received_unix, "gateway_published_unix_ms": unix_ms()}
        if self._publish("motion", value): self.metrics.increment("motion_published")
        else: self.metrics.increment("telemetry_dropped")
        self.metrics.record_processing((time.monotonic_ns() - received_ns) / 1_000_000.0)

    def _publish_health(self, frame) -> None:
        sample = decode_health(frame.payload, time.monotonic_ns())
        value = {"schema_version": SCHEMA_VERSION, "device_id": self.config.gateway.device_id,
                 **asdict(sample), "task_frequency_hz": None, "deadline_miss": None,
                 "stack_remaining_bytes": None, "free_heap_bytes": None,
                 "queue": None, "mutex_timeouts": None, "published_at": utc_iso()}
        if self._publish("health", value): self.metrics.increment("health_published")
        else: self.metrics.increment("telemetry_dropped")

    def _publish_actuator(self, frame) -> None:
        self._actuator_status = decode_actuator_status(frame.payload)
        value = {"schema_version": SCHEMA_VERSION,
                 "device_id": self.config.gateway.device_id,
                 **stable_dict(self._actuator_status), "published_at": utc_iso()}
        if not self._publish("actuator", value):
            self.metrics.increment("telemetry_dropped")

    def _execute_device_command(self, request: MqttCommand) -> tuple[Any, float, int]:
        if self._device is None: raise ConnectionError("serial device offline")
        payload = b""
        if request.command == "set_stream_state":
            enabled = request.params.get("enabled")
            if not isinstance(enabled, bool): raise ValueError("enabled must be boolean")
            payload = bytes((int(enabled),))
        elif request.command == "set_config":
            if self._config is None: raise ValueError("current configuration unavailable")
            allowed = {"sensor_ms", "telemetry_ms", "alpha_milli", "gyro_weight_milli", "log_level", "telemetry_enabled"}
            if not set(request.params).issubset(allowed): raise ValueError("unknown configuration field")
            config = RuntimeConfig(**{**asdict(self._config), **request.params})
            if not config.validate(): raise ValueError("invalid RuntimeConfig")
            payload = config.pack()
        elif request.command in {"actuator_arm", "actuator_disarm",
                                 "actuator_center", "actuator_estop"}:
            if request.params: raise ValueError("this command does not accept params")
            payload = bytes((commands.ACTUATOR_OWNER_MQTT,))
        elif request.command == "actuator_set_target":
            import struct
            if set(request.params) != {"angle_deg"}:
                raise ValueError("actuator_set_target requires angle_deg")
            angle = request.params["angle_deg"]
            if isinstance(angle, bool) or not isinstance(angle, (int, float)) or not -45.0 <= angle <= 45.0:
                raise ValueError("angle_deg must be a finite number within -45..45")
            payload = struct.pack("<Bh", commands.ACTUATOR_OWNER_MQTT,
                                  round(angle * 100.0))
        elif request.params:
            raise ValueError("this command does not accept params")
        before = len(self._device.attempt_results); started = time.monotonic_ns()
        data = self._device.request(COMMAND_IDS[request.command], payload,
                                    retry=request.command not in SIDE_EFFECT_COMMANDS)
        elapsed = (time.monotonic_ns() - started) / 1_000_000.0
        attempts = len(self._device.attempt_results) - before
        if request.command == "get_device_info": result = stable_dict(decode_device_info(data))
        elif request.command == "get_status": result = stable_dict(decode_status(data))
        elif request.command == "get_config": result = stable_dict(RuntimeConfig.unpack(data))
        elif request.command == "get_latest_motion": result = stable_dict(decode_motion(data))
        elif request.command == "actuator_status": result = stable_dict(decode_actuator_status(data))
        else: result = {"accepted": True}
        return result, elapsed, max(1, attempts)

    def _respond(self, value: dict) -> None:
        self._publish("response", value)

    def _handle_command(self, payload: bytes, retained: bool) -> None:
        started = time.monotonic_ns()
        try:
            request = MqttCommand.parse(payload)
        except Exception as exc:
            self.metrics.increment("command_errors"); self._last_error = str(exc); return
        self.metrics.increment("logical_requests")
        cached = self.cache.get(request.request_id)
        if cached is not None:
            self.metrics.increment("duplicate_commands"); self._respond(cached); return
        if retained:
            self.metrics.increment("retained_rejected")
            response = response_payload(request.request_id, request.command, False,
                                        error="RETAINED_COMMAND_REJECTED")
        elif request.expired(maximum_age_s=self.config.limits.maximum_command_age_s):
            self.metrics.increment("expired_commands")
            response = response_payload(request.request_id, request.command, False,
                                        error="COMMAND_EXPIRED")
        else:
            try:
                result, device_ms, attempts = self._execute_device_command(request)
                self.metrics.increment("transport_attempts", attempts)
                self.metrics.increment("safe_retries", attempts - 1)
                self.metrics.increment("command_success")
                response = response_payload(request.request_id, request.command, True, result=result,
                                            device_elapsed_ms=device_ms, transport_attempts=attempts)
            except Exception as exc:
                self.metrics.increment("command_errors"); self._last_error = str(exc)
                response = response_payload(request.request_id, request.command, False, error=str(exc))
        response["gateway_elapsed_ms"] = (time.monotonic_ns() - started) / 1_000_000.0
        self.metrics.record_command(response["gateway_elapsed_ms"])
        self.cache.put(request.request_id, response); self._respond(response)

    def status(self) -> dict:
        return {"schema_version": SCHEMA_VERSION, "gateway_version": __version__,
                "gateway_id": self.config.gateway.gateway_id,
                "device_id": self.config.gateway.device_id,
                "serial_connected": self._device is not None,
                "mqtt_connected": self._mqtt.connected,
                "device_state": self._status.app_state if self._status else "OFFLINE",
                "last_error": self._last_error, "command_queue": self.command_queue.qsize(),
                "metrics": self.metrics.snapshot(), "published_at": utc_iso()}

    def stop(self) -> None: self._stop.set()

    def run(self, duration_s: float | None = None) -> dict:
        deadline = time.monotonic() + duration_s if duration_s else None
        self._mqtt.start(); self._connect_device(); self._publish_online_snapshot()
        serial_backoff = ReconnectBackoff(self.config.serial.reconnect_initial_ms,
                                          self.config.serial.reconnect_max_ms)
        last_state = last_metrics = time.monotonic(); observed_reconnects = 0
        try:
            while not self._stop.is_set() and (deadline is None or time.monotonic() < deadline):
                if self._mqtt.reconnect_count > observed_reconnects:
                    self.metrics.increment("mqtt_reconnects", self._mqtt.reconnect_count - observed_reconnects)
                    observed_reconnects = self._mqtt.reconnect_count
                    self._publish_online_snapshot()
                try:
                    while True:
                        payload, retained = self.command_queue.get_nowait(); self._handle_command(payload, retained)
                except queue.Empty: pass
                if self._device is not None:
                    try:
                        for frame in self._device.poll():
                            self.metrics.increment("device_frames")
                            if frame.type == commands.MOTION_TELEMETRY and self.config.publish.motion_enabled: self._publish_motion(frame)
                            elif frame.type == commands.HEALTH_TELEMETRY and self.config.publish.health_enabled: self._publish_health(frame)
                            elif frame.type == commands.ACTUATOR_TELEMETRY: self._publish_actuator(frame)
                    except Exception as exc:
                        self._last_error = str(exc); self._device.close(); self._device = None
                        self._publish("device_availability", "offline")
                if self._device is None:
                    time.sleep(serial_backoff.next_delay())
                    try:
                        self._connect_device(); serial_backoff.reset()
                        self.metrics.increment("serial_reconnects"); self._publish_online_snapshot()
                    except Exception as exc: self._last_error = str(exc)
                now = time.monotonic()
                if now - last_state >= self.config.publish.status_period_s:
                    self._publish("state", self._state()); self._publish("gateway_state", self.status()); last_state = now
                if now - last_metrics >= self.config.publish.gateway_metrics_period_s:
                    self._publish("gateway_metrics", self._gateway_metrics()); last_metrics = now
        finally:
            if self._device is not None:
                try:
                    if self._original_stream is False:
                        self._device.request(commands.SET_STREAM_STATE, b"\0", retry=False)
                except Exception as exc: self._last_error = str(exc)
                self._device.close(); self._device = None
            self._publish("device_availability", "offline")
            self._publish("gateway_availability", "offline")
            self._mqtt.stop()
        return self.status()
