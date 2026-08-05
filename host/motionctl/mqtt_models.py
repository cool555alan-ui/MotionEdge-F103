"""稳定MQTT JSON模型、UTC时间与远程命令白名单。"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .mqtt_topics import SCHEMA_VERSION

READ_ONLY_COMMANDS = frozenset({"ping", "get_device_info", "get_status",
                                "get_config", "get_latest_motion"})
SIDE_EFFECT_COMMANDS = frozenset({"set_config", "start_calibration",
                                  "set_stream_state"})
ALLOWED_COMMANDS = READ_ONLY_COMMANDS | SIDE_EFFECT_COMMANDS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def unix_ms() -> int:
    return int(utc_now().timestamp() * 1000)


def json_bytes(value: Any) -> bytes:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class MqttCommand:
    schema_version: int
    request_id: str
    command: str
    issued_at: str
    expires_at: str
    params: dict[str, Any]

    @classmethod
    def parse(cls, payload: bytes | str) -> "MqttCommand":
        raw = json.loads(payload.decode("utf-8") if isinstance(payload, bytes) else payload)
        required = {"schema_version", "request_id", "command", "issued_at", "expires_at", "params"}
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError("command fields do not match schema")
        if raw["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported schema_version")
        uuid.UUID(str(raw["request_id"]))
        if raw["command"] not in ALLOWED_COMMANDS:
            raise ValueError("unknown command")
        if not isinstance(raw["params"], dict):
            raise ValueError("params must be an object")
        for key in ("issued_at", "expires_at"):
            datetime.fromisoformat(str(raw[key]).replace("Z", "+00:00"))
        return cls(**raw)

    def expired(self, now: datetime | None = None, maximum_age_s: int = 30) -> bool:
        current = now or utc_now()
        issued = datetime.fromisoformat(self.issued_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return current > expires or (current - issued).total_seconds() > maximum_age_s


def response_payload(request_id: str, command: str, ok: bool, *, result: Any = None,
                     error: str | None = None, elapsed_ms: float = 0.0,
                     device_elapsed_ms: float | None = None,
                     logical_attempts: int = 1, transport_attempts: int = 1) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "request_id": request_id,
            "command": command, "ok": ok, "result": result,
            "error": error, "gateway_elapsed_ms": elapsed_ms,
            "device_elapsed_ms": device_elapsed_ms,
            "logical_attempts": logical_attempts,
            "transport_attempts": transport_attempts,
            "completed_at": utc_iso()}
