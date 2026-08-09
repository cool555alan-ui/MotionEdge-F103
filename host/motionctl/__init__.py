"""MotionEdge binary device protocol tools."""

__version__ = "0.8.0"

from .device import DeviceClient, SimulatedDevice, TimeoutError
from .protocol import Frame, FrameParser, crc16_ccitt_false, decode_frame, encode_frame

__all__ = [
    "DeviceClient",
    "Frame",
    "FrameParser",
    "SimulatedDevice",
    "TimeoutError",
    "crc16_ccitt_false",
    "decode_frame",
    "encode_frame",
    "__version__",
]
