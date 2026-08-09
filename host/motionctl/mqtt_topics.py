"""Phase 7 MQTT Topic契约及QoS/retain规则的唯一来源。"""

from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TopicRule:
    topic: str
    qos: int
    retain: bool


@dataclass(frozen=True)
class TopicSet:
    device_id: str
    gateway_id: str

    def _device(self, suffix: str) -> str:
        return f"motionedge/v1/devices/{self.device_id}/{suffix}"

    def _gateway(self, suffix: str) -> str:
        return f"motionedge/v1/gateways/{self.gateway_id}/{suffix}"

    @property
    def device_availability(self): return self._device("availability")
    @property
    def meta(self): return self._device("meta")
    @property
    def state(self): return self._device("state")
    @property
    def motion(self): return self._device("telemetry/motion")
    @property
    def health(self): return self._device("telemetry/health")
    @property
    def actuator(self): return self._device("telemetry/actuator")
    @property
    def control(self): return self._device("telemetry/control")
    @property
    def events(self): return self._device("events")
    @property
    def command(self): return self._device("command")
    @property
    def response(self): return self._device("response")
    @property
    def gateway_availability(self): return self._gateway("availability")
    @property
    def gateway_state(self): return self._gateway("state")
    @property
    def gateway_metrics(self): return self._gateway("metrics")

    def rules(self, qos_telemetry: int = 0, qos_state: int = 1,
              qos_command: int = 1) -> dict[str, TopicRule]:
        return {
            "device_availability": TopicRule(self.device_availability, 1, True),
            "meta": TopicRule(self.meta, qos_state, True),
            "state": TopicRule(self.state, qos_state, True),
            "motion": TopicRule(self.motion, qos_telemetry, False),
            "health": TopicRule(self.health, qos_telemetry, False),
            "actuator": TopicRule(self.actuator, qos_telemetry, False),
            "control": TopicRule(self.control, qos_telemetry, False),
            "events": TopicRule(self.events, 1, False),
            "command": TopicRule(self.command, qos_command, False),
            "response": TopicRule(self.response, qos_command, False),
            "gateway_availability": TopicRule(self.gateway_availability, 1, True),
            "gateway_state": TopicRule(self.gateway_state, qos_state, True),
            "gateway_metrics": TopicRule(self.gateway_metrics, qos_state, False),
        }
