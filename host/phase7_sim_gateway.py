from __future__ import annotations

import argparse

from motionctl.gateway import Gateway
from motionctl.gateway_config import load_gateway_config
from motionctl.gateway_validation import StreamingSimulatedDevice

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True); parser.add_argument("--duration", type=float)
args = parser.parse_args()
gateway = Gateway(load_gateway_config(args.config), transport_factory=lambda *a, **k: StreamingSimulatedDevice())
gateway.run(args.duration)
