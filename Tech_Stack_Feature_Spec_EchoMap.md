# Tech Stack & Feature Specification --- Accessible 3D Mapping Web App

**Working title:** EchoMap\
**Version:** 0.1 --- Prototype MVP\
**Primary flow:** ESP32 → USB Serial → Next.js web app → 3D directional
scan → local saved sessions

------------------------------------------------------------------------

## 1. Technology choices

  -----------------------------------------------------------------------
  Layer                   Recommended technology  Purpose
  ----------------------- ----------------------- -----------------------
  Framework               Next.js App Router +    Application shell,
                          React + TypeScript      routing, typed
                                                  components

  Styling                 Tailwind CSS            Layout, responsive
                                                  design, design tokens

  Component system        Shannon UI, where       Consistent buttons,
                          compatible; otherwise   cards, dialogs, tabs
                          wrap/adapt components   and status elements
                          behind a small          
                          app-level UI layer      

  Map / map-like controls MapsUI components where Session/map navigation
                          applicable and          or supporting UI; do
                          compatible              not treat a geographic
                                                  map library as the 3D
                                                  sensor renderer

  3D rendering            Three.js + React Three  Live 3D scene
                          Fiber                   

  3D helpers              `@react-three/drei`     Orbit controls, grids,
                                                  axes, labels and camera
                                                  helpers

  Motion                  Framer Motion / Motion  Page transitions and
                          for React               restrained UI
                                                  micro-interactions

  Gradient elements       CSS gradients, Tailwind Background accents and
                          utilities, optional     emphasis; maintain
                          small reusable gradient contrast
                          primitives              

  Serial connection       Web Serial API          User-authorized USB
                                                  serial communication in
                                                  supported desktop
                                                  browsers

  Validation              Zod                     Validate incoming
                                                  serial messages and
                                                  imported scan files

  Local persistence       IndexedDB using `idb`   Store scan sessions and
                          or Dexie                metadata locally

  Data visualization      Three.js                Render scan points and
                          points/instanced        sensor telemetry
                          markers; small charts   
                          optional                

  Icons                   Lucide React            Consistent iconography

  Testing                 Vitest + React Testing  Parser, state, UI and
                          Library; Playwright for workflow testing
                          key flows               

  Code quality            ESLint + Prettier       Linting and formatting

  Deployment              Vercel or another       Web deployment; Web
                          HTTPS-capable host      Serial requires a
                                                  supported secure
                                                  context, with localhost
                                                  usable for development
  -----------------------------------------------------------------------

### Package installation baseline

Use versions compatible with the selected Next.js release and lock them
in the package manager. Typical packages:

``` bash
npm install three @react-three/fiber @react-three/drei
npm install framer-motion lucide-react zod idb
npm install
npm install -D vitest @testing-library/react @testing-library/jest-dom
```

Install and validate Shannon UI and MapsUI from their actual project
documentation before assuming package names or APIs. Treat them as
design-system integrations, not mandatory runtime dependencies until
compatibility is verified. Avoid adding multiple component libraries
that duplicate the same responsibilities.

## 2. Important platform constraints

### Web Serial

-   Web Serial requires a browser that implements the API, normally
    Chromium-based desktop browsers.
-   The user must initiate port selection through a user gesture.
-   Production deployment should use HTTPS; `localhost` is suitable for
    local development.
-   Serial access may not work in Safari, Firefox, many mobile browsers,
    or embedded webviews.
-   Provide a clear unsupported-browser message and a demo-data mode.

### Three-dimensional mapping

-   The MVP visualizes measured range samples. It does not reconstruct
    reliable room geometry from one fixed HC-SR04.
-   A range sample can be placed in 3D only when a direction/orientation
    estimate is available.
-   The MPU6050 can estimate tilt and short-term motion, but
    accelerometer integration drifts and gyroscope yaw drifts. It is not
    a standalone absolute positioning system.
-   Until sensor orientation and scan movement are calibrated, render
    points in a relative/approximate scan frame and communicate that
    limitation in the UI.

### Web-based harmonic feedback

-   Use a visual pulse/ring or waveform animation as the default
    proximity feedback.
-   Optional audio tones must be opt-in, have a volume control, and
    never be the sole source of information.
-   A webpage cannot reliably create physical vibration on a desktop.
    `navigator.vibrate()` support is limited and device-dependent; keep
    it optional and nonessential.
-   Respect `prefers-reduced-motion` and offer a static feedback mode.

## 3. Application architecture

``` text
ESP32 firmware
  ├─ HC-SR04 distance sample
  ├─ MPU6050 accelerometer / gyroscope sample
  └─ newline-delimited serial message
          |
          v
Web Serial adapter
          |
          v
Serial line decoder + Zod validation
          |
          v
Typed sensor event stream
   ├─ Telemetry state
   ├─ Scan session controller
   ├─ Proximity classification
   └─ Diagnostics / sample history
          |
          v
UI state store
   ├─ Sensor dashboard
   ├─ Three.js / React Three Fiber viewer
   ├─ Harmonic feedback panel
   └─ Saved-session manager
          |
          v
IndexedDB
   ├─ Session metadata
   ├─ Samples
   └─ Calibration / protocol version
```

Recommended state separation: - **Connection state:** serial port,
reader/writer lifecycle, connection errors. - **Telemetry state:** most
recent valid readings and freshness. - **Scan state:** idle, recording,
paused, finished. - **Persistence state:** loading, saving, saved,
export/import error. - **Preferences:** thresholds, motion/audio
settings, visual theme.

Use a small state store (React context or Zustand if state complexity
warrants it). Do not put the entire sample history into frequently
rerendering component state; batch UI updates and bound the live-render
buffer.

## 4. Proposed project structure

``` text
src/
  app/
    layout.tsx
    page.tsx
    sessions/
      page.tsx
    settings/
      page.tsx
  components/
    app-shell/
    device/
      connect-device.tsx
      connection-status.tsx
      serial-console.tsx
    telemetry/
      distance-card.tsx
      imu-panel.tsx
      sensor-health.tsx
    scan/
      scan-toolbar.tsx
      scan-viewer.tsx
      scan-legend.tsx
      scan-status.tsx
    feedback/
      harmonic-pulse.tsx
      proximity-status.tsx
    sessions/
      session-list.tsx
      session-detail.tsx
    ui/
      # Shannon UI adapters / app-level wrappers
  lib/
    serial/
      web-serial.ts
      line-decoder.ts
      protocol.ts
    sensors/
      distance.ts
      imu.ts
      proximity.ts
      calibration.ts
    mapping/
      coordinate-transform.ts
      sample-to-point.ts
      scan-buffer.ts
    storage/
      db.ts
      sessions.ts
      import-export.ts
    validation/
      sensor-message.ts
      scan-file.ts
    accessibility/
      announcements.ts
  hooks/
    use-serial-device.ts
    use-scan-session.ts
    use-preferences.ts
  types/
    sensor.ts
    scan.ts
```

Because Web Serial and Three.js depend on browser APIs, place the
relevant components behind client boundaries (`"use client"`). Avoid
accessing `navigator`, `window`, Web Serial or WebGL during server-side
rendering.

## 5. Serial protocol

Prefer one JSON object per line, terminated by `\n`. Version the
protocol so firmware and app can evolve independently.

Example distance + IMU record:

``` json
{
  "v": 1,
  "type": "sample",
  "ts_ms": 123456,
  "distance_cm": 82.4,
  "echo_valid": true,
  "accel_m_s2": { "x": 0.1, "y": 0.2, "z": 9.7 },
  "gyro_rad_s": { "x": 0.01, "y": 0.02, "z": 0.0 }
}
```

Example no-echo record:

``` json
{
  "v": 1,
  "type": "sample",
  "ts_ms": 123956,
  "distance_cm": null,
  "echo_valid": false
}
```

Protocol requirements: - One record per line; UTF-8 text. - `v` is the
protocol version. - Use `null` plus `echo_valid: false` for timeout/no
echo. Never encode timeout as `0`. - ESP32 timestamp is a
device-relative millisecond counter, not wall-clock time. - Parser must
tolerate malformed records and report diagnostic counts. - Add
orientation fields only when their semantics are defined; do not label
raw acceleration as position or absolute heading. - Start with 115200
baud unless firmware is deliberately configured otherwise.

## 6. Data model

### SensorSample

-   `id`: generated sample identifier
-   `receivedAt`: browser receive timestamp
-   `deviceTsMs`: optional ESP32 timestamp
-   `distanceCm`: number or null
-   `echoValid`: boolean
-   `accel`: optional x/y/z in m/s²
-   `gyro`: optional x/y/z in rad/s
-   `orientation`: optional calibrated angles with a documented
    convention
-   `quality`: valid, timeout, malformed, outlier or stale

### ScanSession

-   `id`
-   `name`
-   `createdAt`
-   `updatedAt`
-   `durationMs`
-   `sampleCount`
-   `protocolVersion`
-   `sensorConfig`
-   `calibration`
-   `samples`
-   `notes` (optional)

Use a versioned export format, for example `echomap-scan-v1.json`.
Validate imported files before storing them and limit import size to
prevent browser memory exhaustion.

## 7. 3D scan behaviour

### MVP representation

-   Render each valid sample as a point/marker in a local relative
    coordinate frame.
-   If calibrated direction data is not available, use a directional
    strip, radial plot or explicitly approximate visualization rather
    than inventing spatial coordinates.
-   Include axes, ground grid, distance scale, point count and legend.
-   Provide orbit, pan, zoom, reset view and top view.
-   Color/shape may encode distance bands, but include a textual label
    so color is not the only signal.
-   Provide a bounded live buffer (configurable, e.g. latest 2,000
    points) and persist full session samples separately.
-   Add an explicit **Clear current scan** action with confirmation if
    the session is recording.

### Future extension points

-   Multi-sensor identity and mounting-angle metadata.
-   Pan/tilt encoder or known scan trajectory.
-   Point-cloud filtering and occupancy-grid generation.
-   SLAM/localization backend once appropriate sensing and odometry
    exist.
-   Map versioning and map alignment.

## 8. Feature specification

### A. Device connection

-   Connect, disconnect, connection status, selected baud rate, basic
    diagnostic output.
-   User-gesture-only port selection.
-   Robust cleanup of reader/writer locks on disconnect.

### B. Telemetry

-   Distance in cm.
-   IMU axes with units.
-   Last sample age and sample rate.
-   Invalid/no-echo and stale-data states.
-   Demo mode.

### C. Scan controls

-   Start, pause, resume, finish, clear.
-   Scan timer and sample count.
-   Unsaved-changes state.
-   Session name prompt on save.

### D. 3D viewer

-   Interactive Three.js scene.
-   Orbit/pan/zoom and camera reset.
-   Axes/grid/distance scale.
-   Approximation disclaimer.
-   Accessible alternatives and a text sample list/summary.

### E. Saved sessions

-   IndexedDB persistence.
-   Session list and metadata.
-   Load, rename, delete, export JSON, import JSON.
-   Empty state and storage-error state.

### F. Harmonic feedback

-   Animated pulse intensity maps to configurable proximity bands.
-   Static equivalent for reduced-motion preference.
-   Optional user-enabled sound with volume control.
-   Text announcement for meaningful band changes, with throttling.
-   No claim of physical haptics.

### G. Settings

-   Baud rate.
-   Proximity thresholds.
-   Reduced motion.
-   Audio enable/volume.
-   Point-buffer limit.
-   Coordinate/calibration information.
-   Clear local data with confirmation.

## 9. Visual design direction

### Design language

-   Clean, calm, high-contrast, technical but approachable.
-   Shannon UI for consistent controls where compatible.
-   MapsUI only for components that fit the app's map/session
    information architecture; Three.js remains the 3D sensor
    visualization engine.
-   Gradient elements should be restrained accents, not backgrounds
    behind critical text.
-   Use clear typography, ample spacing, readable units, strong focus
    rings and explicit connection states.
-   Dark theme can support the technical 3D viewer, but provide
    sufficient contrast and avoid low-contrast neon text.

### Suggested workspace layout

1.  Top bar: product name, connection state, settings.
2.  Left/control column: Connect device, sensor health, live telemetry,
    scan controls.
3.  Main canvas: 3D scan viewer and camera controls.
4.  Right/secondary panel: proximity pulse, scan statistics, current
    session.
5.  Saved sessions accessible through a dedicated page or drawer.

### Harmonic element

Create a reusable `HarmonicPulse` component with: - proximity band
input, - intensity level, - static/reduced-motion mode, - optional audio
state, - accessible text label. The visual effect must not obscure
readings or trigger continuous motion when reduced motion is enabled.

## 10. Testing plan

### Unit tests

-   JSON line decoder, partial chunks and multiple lines.
-   Schema validation for valid, malformed, timeout and unknown-version
    records.
-   Distance/proximity band classification.
-   Coordinate conversion and calibration functions.
-   Session serialization and import validation.

### Integration tests

-   Simulated serial stream updates telemetry.
-   Disconnect and malformed input leave the app usable.
-   Start/pause/resume/finish and save/load workflows.
-   IndexedDB errors are shown clearly.

### End-to-end tests

-   Demo mode scan flow.
-   Save and reload a session.
-   Export and re-import a scan.
-   Keyboard navigation and reduced-motion preference.
-   Manual hardware test in supported Chromium browser; automated CI
    should not require a physical ESP32.

## 11. Build sequence

1.  Create Next.js TypeScript app, Tailwind and lint/test setup.
2.  Establish visual tokens and Shannon UI adapters; validate MapsUI
    compatibility.
3.  Build demo-mode dashboard and static 3D viewer.
4.  Define the serial JSON protocol and firmware output.
5.  Implement Web Serial connection and parser.
6.  Connect live samples to telemetry and scan buffer.
7.  Implement session lifecycle and IndexedDB.
8.  Add JSON import/export.
9.  Add harmonic visual feedback and accessibility preferences.
10. Test with the physical ESP32 and document calibration limits.

## 12. Definition of done

-   The app starts locally and has a usable demo mode.
-   Compatible desktop browser can connect to the ESP32 over USB serial
    after user permission.
-   Valid and invalid readings are represented correctly.
-   The viewer is interactive and does not claim full room
    reconstruction.
-   Sessions persist locally and can be exported/imported.
-   Keyboard access, status text, contrast and reduced-motion behaviour
    have been checked.
-   No cloud service, LLM, SLAM, or physical vibration is implied to
    exist in the MVP.
