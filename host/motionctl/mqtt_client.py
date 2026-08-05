"""Paho生命周期封装；不理解串口协议或业务命令。"""

from __future__ import annotations

import threading
import random
from typing import Callable

from .gateway_config import MqttConfig


class MqttClient:
    def __init__(self, config: MqttConfig, *, will_topic: str, will_payload: bytes,
                 on_message: Callable[[str, bytes, bool], None]) -> None:
        import paho.mqtt.client as mqtt
        self._mqtt = mqtt
        self.config = config
        self._on_message_user = on_message
        self._connected = threading.Event()
        self._ever_connected = False
        self.reconnect_count = 0
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                   client_id=config.client_id,
                                   protocol=mqtt.MQTTv311, clean_session=True)
        self._client.max_queued_messages_set(64)
        self._client.reconnect_delay_set(config.reconnect_initial_ms / 1000.0,
                                         config.reconnect_max_ms / 1000.0)
        self._client.will_set(will_topic, will_payload, qos=1, retain=True)
        if config.username:
            self._client.username_pw_set(config.username, config.password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._subscriptions: list[tuple[str, int]] = []

    @property
    def connected(self) -> bool: return self._connected.is_set()

    def add_subscription(self, topic: str, qos: int) -> None:
        self._subscriptions.append((topic, qos))
        if self.connected: self._client.subscribe(topic, qos=qos)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if getattr(reason_code, "value", reason_code) == 0:
            if self._ever_connected: self.reconnect_count += 1
            self._ever_connected = True
            self._connected.set()
            for topic, qos in self._subscriptions: client.subscribe(topic, qos=qos)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self._connected.clear()
        initial = self.config.reconnect_initial_ms / 1000.0
        maximum = self.config.reconnect_max_ms / 1000.0
        client.reconnect_delay_set(min(maximum, initial * random.uniform(1.0, 1.1)), maximum)

    def _on_message(self, client, userdata, message) -> None:
        self._on_message_user(message.topic, bytes(message.payload), bool(message.retain))

    def start(self, timeout_s: float = 5.0) -> None:
        self._client.connect_async(self.config.host, self.config.port, self.config.keepalive_s)
        self._client.loop_start()
        if not self._connected.wait(timeout_s):
            self.stop()
            raise ConnectionError("MQTT broker connection timeout")

    def publish(self, topic: str, payload: bytes | str, *, qos: int, retain: bool) -> bool:
        if not self.connected: return False
        info = self._client.publish(topic, payload, qos=qos, retain=retain)
        return info.rc == self._mqtt.MQTT_ERR_SUCCESS

    def stop(self) -> None:
        try:
            if self.connected: self._client.disconnect()
        finally:
            self._client.loop_stop()
            self._connected.clear()
