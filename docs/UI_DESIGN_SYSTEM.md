# ESM UI Design System & Engineering Specification

## 1. Design Direction: IEEE-Inspired Engineering Aesthetic

The **ESM — Spatial Awareness System** employs an IEEE-inspired visual language prioritizing functional density, high contrast, scientific discipline, and accessibility.

---

## 2. Color Palette Specification

| Token Name | Hex Code | Purpose / Usage |
|---|---|---|
| **Background** | `#071321` | Deep blue-black canvas background |
| **Panel Surface** | `#0D1B2A` | Primary container surfaces (sidebar, cards) |
| **Raised Panel** | `#13263A` | Elevated interactive modules and active headers |
| **Engineering Blue** | `#0878D1` | Primary action buttons, brand accents, technical highlights |
| **Telemetry Cyan** | `#00D1E8` | Live sensor streams, valid echoes, active scan cone |
| **Active Teal** | `#00C2A8` | Positive health status, origin coordinate anchor |
| **Warning Amber** | `#F5A623` | Caution ranges (1.5m - 3.0m), gyro drift warnings, demo labels |
| **Critical Red** | `#EF4444` | Immediate proximity warning (< 1.5m), hardware error state |
| **Text Primary** | `#F4F7FB` | High-contrast headings and primary metrics |
| **Text Secondary** | `#9FB1C5` | Subtitles, parameter units, secondary telemetry |
| **Border Line** | `#263B50` | Structural dividers, module borders, technical grid lines |

---

## 3. Typography & Hierarchy

- **Primary Sans:** `'Manrope'`, system fallback `sans-serif` (optimized for readability).
- **Technical Monospace:** `'DM Mono'`, system fallback `Consolas, monospace` (telemetry, coordinates, numerical metrics).

### Scale:
- **Display 1:** 26px / 700 / letter-spacing -0.8px (Page Title)
- **H2:** 14px / 700 / letter-spacing -0.2px (Panel Titles)
- **Metric Value:** 28px / 800 / letter-spacing -1.0px (Numerical Readouts)
- **Body / Labels:** 12px / 500 / line-height 1.5
- **Monospace Tags:** 9px / 500 / uppercase / letter-spacing 1.2px

---

## 4. Layout Architecture (Four Coordinated Regions)

```
+-----------------------------------------------------------------------------------------------+
| TOPBAR: Breadcrumb / System Status / Demo Mode Switch / Audio Alert Toggle / Preferences      |
+-------------+---------------------------------------------------+-----------------------------+
| REGION A:   | REGION C:                                         | REGION B:                   |
| Left Nav    | Human-Centric Spatial View                        | Forward Camera & Perception |
| - Workspace | - 3D Rigged Human Avatar at Origin (0,0,0)        | - Laptop Webcam Live Feed   |
| - Camera    | - Smart-Glass Directional Scan Cone               | - Device Selector & FPS     |
| - Spatial   | - Layered 3D Assets (Human/Indoor/Street)         | - Fullscreen Expand Modal   |
| - Sessions  | - Provenance Legend: Measured/Estimated/Context   +-----------------------------+
| - Diag      | - Scale Markers (0m, 2m, 4m, 6m) & Grid           | REGION D:                   |
| - Library   |                                                   | Sensor & Session Telemetry  |
| - Prefs     |                                                   | - Real-time Range & IMU     |
|             |                                                   | - Harmonic Proximity Arc    |
|             |                                                   | - Session Recording / Save  |
+-------------+---------------------------------------------------+-----------------------------+
```

---

## 5. Interaction & Accessibility States

1. **Disconnected / Standby:** Clear muted status (`STANDBY`), USB connect prompt.
2. **Connecting:** Pulsing amber indicator with progress copy.
3. **Connected & Streaming:** Real-time green/cyan indicator with live sample counter.
4. **Stale Data Warning:** Automatically surfaces if $>2000\text{ ms}$ elapse without new hardware samples.
5. **Reduced Motion:** Fully complies with `prefers-reduced-motion` CSS and Three.js demand-render loops.
