# Level 3: Relative spatial mapping

## What changed
- Removed generated/demo point-cloud data. The map starts empty and only records points derived from valid ESP32 samples while capture is active.
- Converts centimetres to metres and projects range into local XYZ coordinates.
- Integrates the MPU6050 Y-axis gyro for relative yaw; estimates pitch/roll from accelerometer gravity when the device is not accelerating strongly.
- Applies a rolling median to range samples and rejects no-echo, out-of-range, and large distance-spike records.
- Caps the active point cloud at 2,000 points and validates imported point arrays before loading.
- Adds relative-pose reset, map reset, accepted/rejected counters, and last-sample diagnostics.

## Required setup
Use the same ESP32 firmware and wiring from `firmware/EchoMap_ESP32_Level2/` and `docs/HARDWARE_SETUP.md`. Install the Adafruit MPU6050 and Adafruit Unified Sensor Arduino libraries. Connect with Chrome or Edge on localhost/HTTPS at 115200 baud. Close Arduino Serial Monitor before connecting.

## Capture procedure
1. Place the HC-SR04 facing forward and confirm the MPU6050 axes for your physical mounting.
2. Connect the ESP32.
3. Hold the device stationary and approximately level. Click **Zero relative pose** (this resets the relative yaw accumulator; it is not a full sensor-bias calibration).
4. Click **Start scan**, then move slowly while keeping the ultrasonic sensor pointed toward the surfaces you want to sample.
5. Pause before repositioning; save the session when done.

## Coordinate convention
- Origin: sensor location at the time of each sample is *assumed* to be the same fixed origin. This is a major limitation for handheld movement.
- +X: right of initial forward direction; +Y: up; -Z: initial forward direction.
- Range is converted from cm to metres. Relative yaw comes from gyro-Y integration; pitch is estimated from accelerometer gravity.

## Accuracy limitations — read before interpreting the map
This is **not SLAM and not a calibrated 3D room reconstruction**. A single fixed-origin projection cannot infer the sensor's translation as a person walks. MPU6050 has no magnetometer, so yaw drifts, and accelerometer-based tilt is unreliable during motion. The HC-SR04 has a broad beam and can return multipath or edge reflections. The map is therefore an approximate set of directional range points, not a trustworthy wall surface or obstacle-free path. Do not use it for mobility decisions or as a substitute for a cane, guide dog, or established navigation aid.

## Calibration and validation recommended before Level 4
- Measure the sensor mounting transform and verify axis signs with controlled rotations.
- Calibrate HC-SR04 distance against a tape measure at several distances; record offset and error bounds.
- Add a stationary yaw-bias calibration routine and accelerometer calibration.
- For real mapping while walking, add a motion/position source (e.g. visual-inertial odometry, depth camera, or 2D lidar with SLAM). Gyroscope integration alone cannot provide stable position.
- Evaluate against a measured test room and report point error, repeatability, missed detections, and false returns.
