# EchoMap Level 2 — Hardware Integration

## Wiring
- HC-SR04 VCC → ESP32 5V/VIN (only if board VIN provides 5V)
- HC-SR04 GND → common GND
- HC-SR04 TRIG → GPIO 5
- HC-SR04 ECHO → 1.5 kΩ resistor → GPIO18 junction
- GPIO18 junction → 2.2 kΩ resistor → GND
- GY-521 VCC → 3V3
- GY-521 GND → common GND
- GY-521 SDA → GPIO21
- GY-521 SCL → GPIO22

Disconnect USB power before changing wiring. Confirm the resistor values and junction before powering up.

## Flash ESP32 firmware
1. Open `firmware/EchoMap_ESP32_Level2/EchoMap_ESP32_Level2.ino` in Arduino IDE.
2. Install `Adafruit MPU6050` and `Adafruit Unified Sensor` from Library Manager.
3. Select **ESP32 Dev Module** and the correct COM port.
4. Upload at 115200 baud.
5. Open Serial Monitor at 115200 only for diagnostics; close it before connecting the website because one serial port generally cannot be owned by two apps simultaneously.

Firmware prints newline-delimited JSON only, so the browser parser does not have to filter startup text.

## Run website
```bash
npm install
npm run dev
```
Open `http://localhost:3000` in a supported Chromium-based desktop browser. Click **Connect ESP32**, select the ESP32 serial port and grant permission. Close Arduino Serial Monitor first.

Web Serial support is browser-specific. The site must run in a secure context: localhost is fine for development; hosted deployment should use HTTPS.

## Protocol
Each line has `v: 1`, `type: "sample"`, `ts_ms`, `distance_cm`, `echo_valid`, and optional IMU fields. Invalid/no echo is `distance_cm: null` and `echo_valid: false`.

## Current limitations
- This phase reads live data and telemetry but does not claim a calibrated 3D room reconstruction.
- The current point cloud remains an illustrative directional visualization until sensor sweep direction and pose are measured/calibrated.
- MPU6050 values are raw sensor-derived acceleration and angular velocity, not position or reliable absolute yaw.
- Browser disconnect/error handling is basic; Level 3 should harden stream lifecycle and browser/device compatibility.
- Do not use this prototype as a sole mobility aid.
