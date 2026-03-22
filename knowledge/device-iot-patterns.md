# Device & IoT Patterns

## Protocol Selection

| Protocol | When | Transport | Overhead |
|----------|------|-----------|----------|
| MQTT | Default for IoT. Lightweight pub/sub, QoS levels, retained messages | TCP (+ TLS) | Very low |
| CoAP | RESTful for constrained devices, observe pattern | UDP (+ DTLS) | Minimal |
| HTTP/REST | When bandwidth is not a concern, existing API infrastructure | TCP + TLS | High |
| AMQP | Enterprise IoT, complex routing, guaranteed delivery | TCP + TLS | Medium |
| BLE | Proximity sensing, wearables, short-range device communication | Bluetooth | Minimal |
| WebSocket | Real-time dashboard, device monitoring UI | TCP + TLS | Low |

**Default: MQTT for device-to-cloud. HTTP/REST for management APIs.**

## MQTT Fundamentals

### QoS Levels
```
QoS 0: At most once (fire and forget) — telemetry where occasional loss is OK
QoS 1: At least once (acknowledged) — commands, alerts (may duplicate)
QoS 2: Exactly once (4-step handshake) — billing, critical state changes (slowest)
```

### Topic Design
```
Telemetry:  devices/{device_id}/telemetry/{metric}
Commands:   devices/{device_id}/commands/{command_name}
Status:     devices/{device_id}/status
Shadow:     $aws/things/{device_id}/shadow/update  (AWS IoT Core)
Alerts:     devices/{device_id}/alerts/{severity}
OTA:        devices/{device_id}/ota/{version}

Rules:
- Use device_id in topic path (enables per-device authorization)
- Avoid wildcard subscriptions in production (use specific topics)
- Keep topic levels to 5 or fewer
```

## Device Provisioning

### Registration Flow
```
1. Device manufactured with unique identity (serial number, X.509 cert)
2. First boot: device connects to provisioning endpoint
3. Server validates device identity (certificate, claim code, or pre-authorization)
4. Server registers device in registry (metadata, group assignment, policy)
5. Device receives its operational configuration (MQTT endpoint, topics, shadow)
6. Device begins normal operation
```

### Provisioning Methods
| Method | When | Security |
|--------|------|----------|
| Pre-provisioned (per-device cert) | Manufacturing control | Highest |
| Just-in-time (fleet cert + attestation) | Scale provisioning | High |
| Claim-based (claim code + user action) | Consumer devices | Medium |
| QR code / NFC tap | Mobile-assisted setup | Medium |

## Device Shadow / Digital Twin

```
Concept: server-side representation of device state

Reported state: what the device says it is (temperature: 22°C, firmware: v1.2)
Desired state:  what the cloud wants it to be (firmware: v1.3, mode: eco)
Delta:          difference between reported and desired → triggers device action

Flow:
1. Cloud sets desired state: { "firmware": "v1.3" }
2. Shadow calculates delta: { "firmware": "v1.3" } (device has v1.2)
3. Device receives delta notification
4. Device performs update, reports new state: { "firmware": "v1.3" }
5. Delta resolves to empty — device is in sync

Offline handling:
- Shadow stores latest reported state even when device is offline
- Cloud queries shadow, not the device directly
- When device reconnects, it receives accumulated desired state changes
```

### Platform Implementations
| Platform | Feature | Key API |
|----------|---------|---------|
| AWS IoT Core | Device Shadow | UpdateThingShadow, GetThingShadow |
| Azure IoT Hub | Device Twin | Module twin, reported/desired properties |
| Google Cloud IoT | Device state + config | Device state, device config |
| Custom | Build with Redis/DB | Pub/sub for delta notifications |

## Firmware OTA Updates

```
Update lifecycle:
1. CREATE:  build new firmware, sign with private key
2. STAGE:   upload to update service, create update job
3. DEPLOY:  target device group (canary first: 5% of fleet)
4. MONITOR: track update status (downloading, installing, verified, failed)
5. VERIFY:  device reports new version, health check passes
6. EXPAND:  roll out to full fleet after canary verification
7. ROLLBACK: if failure rate > threshold, revert to previous firmware

A/B partition strategy:
  Partition A: running firmware (active)
  Partition B: receives new firmware (inactive)
  On success: mark B as active, A becomes fallback
  On failure: boot from A (automatic rollback)
```

## Constrained Device Patterns

### Memory Constraints (< 256KB RAM)
```
- CBOR over JSON (30-50% smaller, binary encoding)
- Fixed-size buffers (no dynamic allocation)
- Streaming parsers (don't load full message into memory)
- Aggressive data compaction (bitfields, packed structs)
```

### Bandwidth Constraints (LPWAN, Satellite)
```
- Delta updates (send only changed values, not full state)
- Batching (aggregate telemetry, send every N minutes)
- Compression (LZ4 for speed, zstd for ratio)
- Binary protocols (Protobuf, FlatBuffers) over text (JSON)
```

### Battery Constraints
```
- Deep sleep between transmissions (wake on timer or interrupt)
- Duty cycling (active 1%, sleeping 99%)
- Adaptive reporting (frequent when values change, infrequent when stable)
- Server-side aggregation (reduce device-side computation)
```

## Edge Computing

```
When to compute at edge:
  - Latency critical (< 10ms response needed)
  - Bandwidth limited (process locally, send summary)
  - Privacy sensitive (data must not leave premises)
  - Offline operation required (intermittent connectivity)

Edge gateway pattern:
  Devices → Edge Gateway → Cloud
  Edge processes: filtering, aggregation, anomaly detection, local inference
  Cloud processes: ML training, analytics, fleet management, long-term storage

Local inference:
  - TensorFlow Lite (mobile, embedded)
  - ONNX Runtime (cross-platform)
  - Edge Impulse (purpose-built for embedded ML)
```

## Device Security

```
- Mutual TLS: device and server authenticate each other (X.509 certificates)
- Certificate rotation: graceful rotation with overlap period
- Secure boot: verify firmware integrity before execution
- Hardware security: TPM/HSM for key storage (keys never leave the chip)
- Network segmentation: IoT devices on separate VLAN/subnet
- Minimum privilege: device can only access its own topics/resources
- Firmware signing: only signed firmware can be installed
- Anomaly detection: monitor for unusual device behavior (compromised device)
```

## Telemetry and Command Patterns

### Telemetry (device → cloud)
```
- Time-series data (temperature, humidity, location, battery)
- Batch or stream based on connectivity
- Include device_id, timestamp, and measurement in every message
- Store in time-series database (InfluxDB, TimescaleDB, AWS Timestream)
```

### Commands (cloud → device)
```
- Direct method: synchronous, request-response (reboot, diagnostics)
- Desired state: asynchronous, device picks up when ready (config change)
- Command queue: ordered, persistent (firmware update steps)
- Acknowledgment: device confirms command received and executed
```

## Testing IoT Systems

```
Unit:         Test device firmware logic in isolation (mock hardware)
Integration:  Test MQTT message flow (local broker, real protocol)
Device sim:   Simulate fleet of devices for load testing
OTA:          Test update flow on physical device (or emulator)
Security:     Penetration test device endpoints, certificate validation
Connectivity: Test offline behavior, reconnection, message ordering
```
