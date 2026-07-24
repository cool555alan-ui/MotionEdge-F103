# Phase 4: Binary Device Protocol

Phase 4 adds a fixed-memory protocol path from USART1 through a 256-byte ring
buffer, recoverable parser, command service, runtime configuration, and framed
responses. Each application pass reads at most 32 UART bytes and parses at most
64 bytes, preserving the existing 100 Hz sensor path.

CRC, framing, buffering, and parsing are HAL-independent. The only receive HAL
call is the BSP zero-timeout one-byte poll. This is intentionally the minimum
non-blocking integration for the current bare-metal phase; when FreeRTOS is
introduced it should be replaced with interrupt or DMA reception feeding the
same ring buffer.

Runtime configuration updates sample and telemetry periods, low-pass alpha,
complementary-filter gyro weight, log level, and stream state. The full record
is validated before service updates and is stored only in RAM. Motion and
health telemetry use explicit integer serialization as defined in
[the protocol specification](protocol-specification.md).

Verification includes native C tests of CRC, ring boundaries, golden frames,
stream recovery, configuration, command validation, sequence echo, and
telemetry length. Python tests consume the same JSON vectors and cover framing,
split/noisy streams, sequence-matched requests, timeouts, and simulated
commands. The STM32 firmware is also cross-compiled with GCC.

## Validation boundary

No target hardware is connected. Protocol logic, the simulated device, host
tests, and cross-compilation are verified. These results do not verify real
USART electrical behavior, baud accuracy, split-frame timing, command response
latency, sustained streaming, or coexistence with an MPU6050 on a breadboard.

Breadboard validation must cover:

1. ST-LINK flash/debug and clock configuration.
2. USART1 TX/RX wiring, common ground, and 115200 baud.
3. PING, information, status, configuration, calibration, and stream commands.
4. CRC fault injection, split frames, noise recovery, and RX overflow behavior.
5. Motion and health field decoding over a sustained run.
6. Confirmation that protocol mode contains no text/CSV bytes.
7. Phase 1–3 LED, I2C, sensor, calibration, and attitude checks.
