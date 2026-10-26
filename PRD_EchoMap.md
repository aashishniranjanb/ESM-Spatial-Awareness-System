# PRD --- Accessible Environmental Mapping Web App

**Working title:** EchoMap\
**Document type:** Product Requirements Document\
**Version:** 0.1 --- Prototype MVP\
**Status:** Draft for implementation\
**Primary platform:** Desktop browser\
**Hardware:** ESP32 DevKit, HC-SR04 ultrasonic sensor, GY-521 / MPU6050\
**Connection:** USB serial

------------------------------------------------------------------------

## 1. Product vision

Build an accessible, browser-based environmental scanning tool that
receives live measurements from an ESP32 and turns them into an
understandable, interactive 3D directional scan. Users can inspect the
current scan, see sensor status, and save or reload scan sessions.

The project is intended as an early research prototype for assistive
environmental awareness. Future versions may add multiple distance
sensors or ToF sensors, localization and SLAM, vibration hardware, voice
interaction, and language-model-assisted explanations.

**Safety boundary:** This prototype is not a certified mobility aid and
must not be represented as a replacement for a white cane, guide dog, or
trained mobility support.

## 2. Problem statement

A single distance sensor provides isolated range measurements, which are
difficult to interpret as an environment. The prototype needs to make
those measurements visible, understandable, and reusable without
requiring users to read raw serial logs.

## 3. MVP goals

1.  Connect to an ESP32 over USB serial from a compatible desktop
    browser.
2.  Parse and validate incoming sensor records.
3.  Display live distance and MPU6050 readings with connection and
    data-quality states.
4.  Render a live, rotatable 3D directional scan.
5.  Let users start, pause, resume, clear, and finish a scan.
6.  Save scans locally and reopen, rename, and delete them.
7.  Provide accessible controls, readable status messages, keyboard
    navigation, and a reduced-motion option.
8.  Include a non-verbal "harmonic" feedback visualization that can
    express proximity through animated pulses. Audio feedback may be an
    explicit optional setting; visual animation is the default.

## 4. Non-goals for this MVP

-   Full 3D reconstruction of walls or rooms from one fixed ultrasonic
    sensor.
-   SLAM, reliable global positioning, path planning, or autonomous
    navigation.
-   Certified safety alerts or guarantees that an obstacle has been
    detected.
-   Cloud accounts, online sync, or remote AI/LLM calls.
-   Native phone app support.
-   Physical vibration output from the website itself. Physical haptics
    require compatible hardware or a supported device/browser API;
    desktop browser support is inconsistent.
-   Inferring a stable world coordinate frame from MPU6050 readings
    alone.

## 5. Target users and usage context

### Primary

-   Project developers testing sensor acquisition and scan
    visualization.
-   Researchers prototyping accessible spatial awareness tools.
-   Sighted testers helping evaluate the prototype in a controlled
    environment.

### Future

-   Blind and low-vision users participating in supervised usability
    research after safety and accessibility testing.

## 6. User stories

-   As a tester, I can connect to the ESP32 and see whether the serial
    stream is healthy.
-   As a tester, I can see the current distance and sensor
    orientation/motion readings.
-   As a tester, I can start a scan and see samples appear in the 3D
    viewer.
-   As a tester, I can rotate, zoom, pan, and reset the 3D camera.
-   As a tester, I can save a named scan and reload it later.
-   As a tester, I can tell the difference between live measurements,
    stale data, invalid readings, and no echo.
-   As a user with accessibility needs, I can operate the main workflow
    with a keyboard and screen reader.
-   As a user sensitive to motion, I can disable or reduce animated
    effects.

## 7. MVP feature requirements

### 7.1 USB serial connection

-   Provide a clear **Connect device** action that invokes the browser's
    serial-port picker.
-   Provide connection status: Disconnected, Waiting for permission,
    Connected, Reconnecting/Interrupted, and Error.
-   Support a configurable baud rate, defaulting to 115200.
-   Provide Disconnect and a small diagnostic log.
-   Do not silently reconnect or access a serial port without a user
    gesture.
-   Show a compatibility message when Web Serial is unavailable. Target
    Chromium-based desktop browsers over HTTPS or localhost.
-   Handle malformed lines and connection loss without crashing the
    interface.

### 7.2 Sensor dashboard

-   Show live distance in centimetres.
-   Show accelerometer X/Y/Z in m/s² and gyroscope X/Y/Z in rad/s when
    present.
-   Show last-update time and data freshness.
-   Distinguish a valid distance from timeout/no echo; never render
    timeout as zero centimetres.
-   Display a clear notice that IMU measurements are not a reliable
    position estimate.

### 7.3 Live directional scan

-   Display a 3D scene using a point/marker representation for measured
    samples.
-   Each sample contains timestamp, range, and orientation values if
    supplied.
-   Use a documented coordinate convention and configurable calibration
    constants.
-   Until calibrated sensor direction and device movement are known,
    label the view **Directional scan / approximate**, not a room map.
-   Provide orbit, pan, zoom, reset-camera, top-view, and clear-scan
    controls.
-   Show distance scale, axes, grid, and a legend.
-   Provide a sample-data/demo mode that works without connecting
    hardware.
-   Keep rendering responsive by bounding the live point history and
    allowing older data to be stored in the scan file.

### 7.4 Scan session management

-   Start, pause, resume, finish, clear, save, and load a scan.
-   Ask for a session name when saving; record creation time,
    firmware/protocol version, sensor configuration, sample count, and
    calibration metadata.
-   Store sessions locally in browser storage (IndexedDB preferred for
    larger datasets).
-   Support rename and delete with confirmation.
-   Export a session as JSON and import a previously exported JSON file.
-   Clearly explain that local browser data may be lost if site data is
    cleared; exported JSON is the portable backup.
-   No cloud upload in MVP.

### 7.5 Harmonic proximity feedback

-   Provide a simple animated pulse/ring visualization linked to
    measured proximity.
-   Define proximity bands as configurable prototype thresholds (example
    defaults: Near ≤ 50 cm, Medium ≤ 150 cm, Far \> 150 cm); label these
    as experimental, not safety-certified.
-   Make animation optional and honor `prefers-reduced-motion`.
-   Optionally provide a quiet audio tone after an explicit user opt-in
    and volume control.
-   Do not imply the website can physically vibrate the user. Physical
    vibration is a future hardware feature; `navigator.vibrate()` is not
    consistently supported on desktop and should never be a core
    requirement.
-   Provide textual status alongside all animation/audio cues.

### 7.6 Accessibility and usability

-   Semantic page regions and headings.
-   Keyboard-operable controls with visible focus states.
-   Accessible names and status announcements for connection state and
    meaningful proximity changes, avoiding overly frequent screen-reader
    announcements.
-   High contrast and a non-color-only status system using
    text/icons/shapes.
-   Responsive layout for common laptop and tablet widths; desktop
    Chromium is the MVP target due to Web Serial.
-   Reduced-motion setting; audio disabled by default.
-   Do not rely on 3D visualization as the only way to understand
    status.

## 8. Information architecture

1.  **Scan workspace**
    -   Device connection
    -   Live distance and IMU metrics
    -   3D scan viewer
    -   Scan controls
    -   Harmonic feedback panel
2.  **Saved sessions**
    -   Session list, metadata, preview, load, rename, export, delete
3.  **Settings**
    -   Serial baud rate
    -   Proximity thresholds
    -   Visualization preferences
    -   Reduced motion and optional audio
    -   Calibration and coordinate convention
4.  **Help / limitations**
    -   Supported browser
    -   Hardware wiring
    -   Sensor limitations
    -   Safety notice

## 9. Acceptance criteria

-   User can connect to a compatible serial device after explicitly
    selecting it.
-   Valid distance samples update the dashboard and scan viewer without
    page reload.
-   No-echo and malformed messages are visibly distinguished from real
    distance readings.
-   Disconnecting the USB cable produces a clear disconnected state
    without crashing the page.
-   A user can save a scan, refresh the page, and reload it from local
    storage.
-   A saved scan can be exported and imported as JSON.
-   3D viewer controls work by mouse/touch where available and have
    accessible labelled alternatives for key actions.
-   Reduced-motion mode disables nonessential continuous animation.
-   Demo mode demonstrates the workflow without hardware.
-   The app labels the current result as a directional scan and does not
    claim SLAM or accurate room reconstruction.

## 10. Success metrics for the prototype

-   Connection success rate during controlled testing.
-   Time from opening the app to first valid sensor reading.
-   Percentage of valid serial samples parsed.
-   UI responsiveness during a 10-minute scan.
-   Save/reload/export/import success.
-   Number of accessibility blockers found during keyboard and
    screen-reader review.
-   Qualitative clarity of scan status and proximity feedback in
    supervised testing.

## 11. Risks and mitigations

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  Web Serial unsupported in some      Detect capability, explain
  browsers                            supported environment, provide demo
                                      mode

  One sensor produces sparse spatial  Label as directional scan; plan for
  data                                sensor sweep or multiple sensors

  MPU6050 drift makes point placement Do not treat IMU readings as
  misleading                          absolute position; expose
                                      calibration and uncertainty

  Ultrasonic reflections or missed    Filter outliers, show
  echoes                              invalid/no-echo state, preserve raw
                                      samples in logs

  Web animation mistaken for physical Label it as visual feedback; keep
  haptics                             hardware vibration as a future
                                      phase

  Accessibility is undermined by      Pair the viewer with text, metrics,
  3D-only UI                          status and keyboard controls

  Local data loss                     Use IndexedDB and provide explicit
                                      JSON export/import
  -----------------------------------------------------------------------

## 12. Future roadmap

-   **Phase 1:** USB serial, live sensor dashboard, directional 3D scan,
    saved sessions.
-   **Phase 2:** More directional sensors or a controlled scanning
    mechanism; calibration and improved filtering.
-   **Phase 3:** ToF sensor evaluation and denser range data.
-   **Phase 4:** Position estimation and SLAM using suitable
    sensing/odometry.
-   **Phase 5:** Physical vibration feedback and accessible navigation
    cues.
-   **Phase 6:** Offline voice commands and optional SLM/LLM integration
    for natural-language summaries, with critical obstacle logic
    remaining local.

## 13. Open implementation decisions

-   Final serial message format and firmware versioning.
-   Actual resistor/sensor configuration and calibration procedure.
-   Whether orientation values are transmitted by firmware in the first
    firmware revision.
-   Chosen persistent-storage schema and scan-file version.
-   Exact design-system packages and their compatibility with the chosen
    Next.js version.
