"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, AudioLines, Bookmark,
  Camera, Check, ChevronDown, Download, Eye, FileUp, Focus, Gauge, Grid2X2,
  Layers3, Play, Pause, Radio, RotateCcw, Scan, Settings2, ShieldCheck,
  SlidersHorizontal, Sparkles, Target, Timer, Usb, Volume2, VolumeX, Waves, X,
  Box, Cpu, Compass, Maximize2, Minimize2
} from "lucide-react";
import ScanViewer, { type ScanPoint, type VisionOverlay, type PersistentLandmark, type CameraTrajectoryPose } from "@/components/scan-viewer";
import CameraPanel, { type ExtendedVisionOverlay } from "@/components/camera-panel";
import { useSerialDevice } from "@/hooks/use-serial-device";
import type { SensorMessage } from "@/lib/serial/protocol";
import { initialMapperState, projectSample, validateScanPoints, type MapperState } from "@/lib/mapping/spatial";
import { DeterministicDemoSimulator } from "@/lib/simulator/demo-simulator";
import { BackendWSClient, type VisionDetectionPayload, type VisionStatusPayload, type SLAMStatusPayload, type MapUpdatePayload } from "@/lib/backend-client";

type Session = { id: string; name: string; savedAt: string; points: ScanPoint[]; sampleCount: number };
const STORAGE_KEY = "esm.sessions.v1";

export default function Home() {
  // Navigation active view state
  const [activeNav, setActiveNav] = useState<"workspace" | "camera" | "environment" | "sessions" | "diagnostics" | "library" | "preferences">("workspace");

  // Operational Modes: 'hardware' vs 'demo'
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [connected, setConnected] = useState(false);
  const [hardwareDistance, setHardwareDistance] = useState<number | null>(null);
  const [hardwareImu, setHardwareImu] = useState<SensorMessage | null>(null);
  const [lastHardwareAt, setLastHardwareAt] = useState<number | null>(null);
  const [mapper, setMapper] = useState<MapperState>(() => initialMapperState());
  const mapperRef = useRef<MapperState>(initialMapperState());

  // Backend Sync State
  const [backendStatus, setBackendStatus] = useState<"connected" | "disconnected" | "error">("disconnected");
  const wsClientRef = useRef<BackendWSClient | null>(null);
  const [activeBackendSessionId, setActiveBackendSessionId] = useState<string | null>(null);

  // Scanning & UI States
  const scanningRef = useRef(false);
  const pausedRef = useRef(false);
  const [scanning, setScanning] = useState(false);
  const [paused, setPaused] = useState(false);
  const [distance, setDistance] = useState(84.6);
  const [sampleCount, setSampleCount] = useState(0);
  const [points, setPoints] = useState<ScanPoint[]>([]);
  const [visionDetections, setVisionDetections] = useState<ExtendedVisionOverlay[]>([]);
  const [visionStatus, setVisionStatus] = useState<VisionStatusPayload | undefined>(undefined);
  const [slamStatus, setSlamStatus] = useState<SLAMStatusPayload | undefined>(undefined);
  const [persistentLandmarks, setPersistentLandmarks] = useState<PersistentLandmark[]>([]);
  const [cameraTrajectory, setCameraTrajectory] = useState<CameraTrajectoryPose[]>([]);

  // 3D Scene Layer Visibility Toggles
  const [showPointCloud, setShowPointCloud] = useState(true);
  const [showLandmarks, setShowLandmarks] = useState(true);
  const [showTrajectory, setShowTrajectory] = useState(true);
  const [showIllustrative, setShowIllustrative] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const viewerContainerRef = useRef<HTMLDivElement | null>(null);

  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [audioAlertsEnabled, setAudioAlertsEnabled] = useState(false);

  // Replay State
  const [isReplaying, setIsReplaying] = useState(false);
  const [replayProgress, setReplayProgress] = useState(0);
  const [replayEventTotal, setReplayEventTotal] = useState(0);
  const replayTimerRef = useRef<any>(null);

  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionName, setSessionName] = useState("Corridor sweep");
  const [notice, setNotice] = useState("ESM Spatial Awareness System ready. Awaiting hardware or demo run.");
  const [viewMode, setViewMode] = useState<"3d" | "top" | "front">("3d");
  const [showSettings, setShowSettings] = useState(false);
  const [threshold, setThreshold] = useState(60);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [lastSampleNote, setLastSampleNote] = useState("Waiting for sensor telemetry");

  // Demo simulator ref
  const demoSimulatorRef = useRef<DeterministicDemoSimulator>(new DeterministicDemoSimulator(42));
  const demoIntervalRef = useRef<any>(null);

  // Initialize Backend WebSocket
  useEffect(() => {
    const ws = new BackendWSClient(activeBackendSessionId || "global");
    ws.setCallbacks(
      (p) => {
        // Spatial point received from backend if broadcast
      },
      (status) => setBackendStatus(status),
      (realDetections, latency_ms) => {
        if (!isDemoMode) {
          // Rule 1: Represent 2D detections accurately with bounding box, class, conf, track_id.
          // Do NOT place at arbitrary 3D position. Set spatial_coords ONLY if acoustic depth is available.
          const overlays: ExtendedVisionOverlay[] = realDetections.map((d) => {
            const hasDepth = d.acoustic_candidate_dist_m !== undefined && d.acoustic_candidate_dist_m > 0;
            return {
              id: d.id,
              label: d.class_name,
              confidence: d.confidence,
              box_normalized: d.box_normalized,
              track_id: d.track_id,
              overlaps_path_corridor: d.overlaps_path_corridor,
              corridor_overlap_ratio: d.corridor_overlap_ratio,
              is_path_obstruction: d.is_path_obstruction,
              is_approximate: true,
              latency_ms: d.latency_ms,
              uncertainty: d.uncertainty,
              acoustic_candidate_dist_m: d.acoustic_candidate_dist_m,
              has_valid_depth: hasDepth,
              est_distance_m: d.acoustic_candidate_dist_m,
              // Only assign 3D coords when depth is grounded
              spatial_coords: hasDepth
                ? {
                    x: (d.box_normalized.x + d.box_normalized.w / 2 - 0.5) * 2.0 * (d.acoustic_candidate_dist_m || 2.5) * 0.6,
                    y: -(d.box_normalized.y + d.box_normalized.h / 2 - 0.5) * 1.5 * (d.acoustic_candidate_dist_m || 2.5) * 0.45,
                    z: -(d.acoustic_candidate_dist_m || 2.5),
                  }
                : undefined,
            };
          });
          setVisionDetections(overlays);
        }
      },
      (status) => {
        setVisionStatus(status);
      },
      (slam) => {
        setSlamStatus(slam);
      },
      (mapData) => {
        if (mapData.landmarks) {
          setPersistentLandmarks(mapData.landmarks);
        }
      }
    );
    ws.connect();
    wsClientRef.current = ws;

    return () => {
      ws.disconnect();
    };
  }, [activeBackendSessionId, isDemoMode]);

  // Hardware sample arrival handler
  const onHardwareSample = useCallback((sample: SensorMessage) => {
    if (isDemoMode) return; // Do not mix hardware samples in demo mode

    setHardwareImu(sample);
    setConnected(true);
    setLastHardwareAt(Date.now());

    if (sample.echo_valid && typeof sample.distance_cm === "number") {
      setHardwareDistance(sample.distance_cm);
      // Accessible Speech/Audio Alert
      if (audioAlertsEnabled && sample.distance_cm <= threshold) {
        if ("speechSynthesis" in window && !window.speechSynthesis.speaking) {
          const utterance = new SpeechSynthesisUtterance(`Warning. Obstacle at ${Math.round(sample.distance_cm)} centimetres`);
          utterance.rate = 1.2;
          window.speechSynthesis.speak(utterance);
        }
      }
    }

    // Forward to FastAPI Backend WebSocket for real-time persistence
    if (wsClientRef.current) {
      wsClientRef.current.forwardSample(sample);
    }

    const result = projectSample(sample, mapperRef.current);
    mapperRef.current = result.state;
    setMapper(result.state);
    setLastSampleNote(result.reason ?? "Measured point projected into local coordinates");

    if (scanningRef.current && !pausedRef.current && result.point) {
      setPoints((old) => [...old.slice(-1999), result.point!]);
      setSampleCount((n) => n + 1);
    }
  }, [isDemoMode, threshold, audioAlertsEnabled]);

  const serial = useSerialDevice(onHardwareSample);

  // Stale data check
  const isDataStale = useMemo(() => {
    if (!lastHardwareAt || isDemoMode) return false;
    return Date.now() - lastHardwareAt > 2000;
  }, [lastHardwareAt, isDemoMode, sampleCount]);

  // Load saved local sessions
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY) || localStorage.getItem("echomap.sessions.v3");
      if (raw) setSessions(JSON.parse(raw) as Session[]);
    } catch {
      setNotice("Could not read saved sessions from this browser.");
    }
  }, []);

  // Demo Mode Tick loop (Deterministic 4 Hz)
  useEffect(() => {
    if (isDemoMode && scanning && !paused) {
      demoIntervalRef.current = setInterval(() => {
        const { sample, detections } = demoSimulatorRef.current.getNextSample();
        setHardwareImu(sample);
        setDistance(sample.distance_cm || 100);
        setVisionDetections(detections);

        const result = projectSample(sample, mapperRef.current);
        mapperRef.current = result.state;
        setMapper(result.state);
        setLastSampleNote("Deterministic simulation active");

        if (result.point) {
          setPoints((old) => [...old.slice(-1999), result.point!]);
          setSampleCount((n) => n + 1);
        }
      }, 250);
    } else {
      clearInterval(demoIntervalRef.current);
    }

    return () => clearInterval(demoIntervalRef.current);
  }, [isDemoMode, scanning, paused]);

  // Switch between Hardware and Demo
  const toggleDemoMode = () => {
    const nextMode = !isDemoMode;
    setIsDemoMode(nextMode);
    setScanning(false);
    scanningRef.current = false;
    setPaused(false);
    pausedRef.current = false;
    setPoints([]);
    setSampleCount(0);
    mapperRef.current = initialMapperState();
    setMapper(mapperRef.current);

    if (nextMode) {
      demoSimulatorRef.current.reset();
      setNotice("DEMO MODE active: Running deterministic virtual environment with rigged avatar and local 3D assets.");
    } else {
      setVisionDetections([]);
      setPersistentLandmarks([]);
      setNotice("HARDWARE MODE active: Waiting for ESP32 measurements. Points are derived solely from real sensor echoes.");
    }
  };

  // Fullscreen Handler using Browser Fullscreen API
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      viewerContainerRef.current?.requestFullscreen?.().catch((err) => {
        setNotice(`Fullscreen error: ${err.message}`);
      });
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  };

  useEffect(() => {
    const onFsChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFsChange);
    return () => document.removeEventListener("fullscreenchange", onFsChange);
  }, []);

  const shownDistance = !isDemoMode && connected && hardwareDistance !== null ? hardwareDistance : distance;
  const band = shownDistance <= threshold ? "Near" : shownDistance <= 150 ? "Medium" : "Far";
  const proximityWidth = Math.max(8, Math.min(100, (1 - shownDistance / 300) * 100));
  const formattedNow = useMemo(() => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), [sampleCount]);

  function persist(next: Session[]) {
    setSessions(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      setNotice("Session registry updated in local storage.");
    } catch {
      setNotice("Could not save. Browser storage may be full.");
    }
  }

  // Save session to backend as well as local storage
  async function saveSession() {
    const item: Session = {
      id: crypto.randomUUID(),
      name: sessionName.trim() || "Untitled session",
      savedAt: new Date().toISOString(),
      points,
      sampleCount,
    };
    persist([item, ...sessions]);

    // Async persist to FastAPI backend
    try {
      const res = await fetch("http://localhost:8000/api/v1/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: item.name,
          source_mode: isDemoMode ? "demo" : "hardware",
          notes: "Saved via ESM Spatial Awareness System",
        }),
      });
      if (res.ok) {
        const backendSession = await res.json();
        setActiveBackendSessionId(backendSession.id);
        setNotice(`Session “${item.name}” saved locally & synced to backend (${backendSession.id.slice(0, 8)}).`);
      }
    } catch {
      setNotice(`Saved locally in browser. (Backend server unreachable at http://localhost:8000)`);
    }
  }

  function loadSession(session: Session) {
    if (isReplaying) stopReplay();
    setPoints(session.points);
    setSampleCount(session.sampleCount);
    setSessionName(session.name);
    setScanning(false);
    scanningRef.current = false;
    setPaused(false);
    pausedRef.current = false;
    setNotice(`Loaded session “${session.name}”.`);
  }

  function stopReplay() {
    if (replayTimerRef.current) {
      clearInterval(replayTimerRef.current);
      replayTimerRef.current = null;
    }
    setIsReplaying(false);
    setReplayProgress(0);
    setReplayEventTotal(0);
    setNotice("Replay stopped.");
  }

  async function replaySession(session: Session) {
    // 1. Check if backend has the full replay stream
    stopReplay();
    setScanning(false);
    scanningRef.current = false;
    setPaused(false);
    pausedRef.current = false;
    setPoints([]);
    setVisionDetections([]);
    setSampleCount(0);
    setSessionName(session.name);

    try {
      setNotice(`Fetching replay stream for “${session.name}”…`);
      const res = await fetch(`http://localhost:8000/api/v1/sessions/${session.id}/replay`);
      if (res.ok) {
        const replayData = await res.json();
        const events: any[] = replayData.events || [];
        if (events.length === 0) {
          // Fallback to local points stepping
          fallbackLocalReplay(session.points);
          return;
        }

        setIsReplaying(true);
        setReplayEventTotal(events.length);
        let currentIndex = 0;
        setNotice(`Replaying ${events.length} session events in timestamp order…`);

        replayTimerRef.current = setInterval(() => {
          if (currentIndex >= events.length) {
            stopReplay();
            setNotice(`Replay of “${session.name}” complete.`);
            return;
          }

          const ev = events[currentIndex];
          if (ev.type === "spatial.point") {
            setPoints((prev) => [...prev.slice(-1999), ev.data]);
            setSampleCount((n) => n + 1);
          } else if (ev.type === "sensor.sample") {
            if (ev.data.distance_cm) setDistance(ev.data.distance_cm);
          } else if (ev.type === "vision.detection") {
            setVisionDetections([
              {
                id: ev.data.id,
                label: ev.data.label,
                confidence: ev.data.confidence,
                box_normalized: ev.data.box_normalized,
                is_approximate: true,
                est_distance_m: ev.data.est_distance_m || 2.5,
                spatial_coords: ev.data.spatial_coords,
                overlaps_path_corridor: false,
                corridor_overlap_ratio: 0,
                is_path_obstruction: false,
              },
            ]);
          }

          currentIndex++;
          setReplayProgress(currentIndex);
        }, 120); // ~8 Hz playback rate
        return;
      }
    } catch {
      // Backend not running or session not in backend
    }

    // Fallback to local replay using saved points
    fallbackLocalReplay(session.points);
  }

  function fallbackLocalReplay(sessionPoints: ScanPoint[]) {
    if (!sessionPoints || sessionPoints.length === 0) {
      setNotice("No points available in this session to replay.");
      return;
    }
    setIsReplaying(true);
    setReplayEventTotal(sessionPoints.length);
    let idx = 0;
    setNotice(`Replaying ${sessionPoints.length} local points…`);

    replayTimerRef.current = setInterval(() => {
      if (idx >= sessionPoints.length) {
        stopReplay();
        setNotice("Local replay complete.");
        return;
      }
      setPoints((prev) => [...prev, sessionPoints[idx]]);
      setSampleCount((n) => n + 1);
      idx++;
      setReplayProgress(idx);
    }, 100);
  }

  function exportSession(session?: Session) {
    const item = session ?? {
      id: crypto.randomUUID(),
      name: sessionName,
      savedAt: new Date().toISOString(),
      points,
      sampleCount,
    };
    const blob = new Blob([JSON.stringify({ format: "esm-scan-v1", ...item }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${item.name.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "esm-scan"}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setNotice("JSON export downloaded.");
  }

  async function importSession(file?: File) {
    if (!file) return;
    try {
      const data = JSON.parse(await file.text()) as Session & { format?: string };
      if (
        (data.format !== "esm-scan-v1" && data.format !== "echomap-scan-v1" && data.format !== "echomap-scan-v2") ||
        !validateScanPoints(data.points) ||
        typeof data.name !== "string"
      ) {
        throw new Error("Invalid scan file format");
      }
      const item: Session = {
        id: crypto.randomUUID(),
        name: data.name,
        savedAt: new Date().toISOString(),
        points: data.points,
        sampleCount: Number(data.sampleCount) || data.points.length,
      };
      persist([item, ...sessions]);
      loadSession(item);
    } catch {
      setNotice("Import failed: choose a valid ESM or EchoMap JSON session.");
    }
  }

  return (
    <main className={reducedMotion ? "app reduced-motion" : "app"}>
      {/* REGION A: Left Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Compass size={22} /></div>
          <div>
            <strong>ESM<span>.io</span></strong>
            <small>SPATIAL AWARENESS</small>
          </div>
        </div>
        
        <div className="workspace-label">SYSTEM REGIONS</div>
        <button
          className={`nav-item ${activeNav === "workspace" ? "active" : ""}`}
          onClick={() => setActiveNav("workspace")}
        >
          <Scan size={16} /> Live Workspace <span className="nav-dot" />
        </button>
        <button
          className={`nav-item ${activeNav === "camera" ? "active" : ""}`}
          onClick={() => {
            setActiveNav("camera");
            if (!cameraEnabled) setCameraEnabled(true);
          }}
        >
          <Camera size={16} /> Camera & Perception
        </button>
        <button
          className={`nav-item ${activeNav === "environment" ? "active" : ""}`}
          onClick={() => {
            setActiveNav("environment");
            setViewMode(viewMode === "3d" ? "top" : "3d");
          }}
        >
          <Focus size={16} /> Spatial Environment
        </button>
        <button
          className={`nav-item ${activeNav === "sessions" ? "active" : ""}`}
          onClick={() => {
            setActiveNav("sessions");
            document.getElementById("sessions")?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" });
          }}
        >
          <Layers3 size={16} /> Saved Sessions <span className="nav-count">{sessions.length}</span>
        </button>
        <button
          className={`nav-item ${activeNav === "diagnostics" ? "active" : ""}`}
          onClick={() => setActiveNav("diagnostics")}
        >
          <Cpu size={16} /> Sensor Diagnostics
        </button>
        <button
          className={`nav-item ${activeNav === "library" ? "active" : ""}`}
          onClick={() => setActiveNav("library")}
        >
          <Box size={16} /> 3D Asset Library
        </button>
        <button
          className={`nav-item ${activeNav === "preferences" ? "active" : ""}`}
          onClick={() => setShowSettings(!showSettings)}
        >
          <Settings2 size={16} /> Preferences
        </button>

        <div className="sidebar-spacer" />

        <div className="safety-card">
          <ShieldCheck size={18} />
          <div>
            <strong>Assistive Prototype</strong>
            <p>Not a certified mobility aid. A single ultrasonic beam cannot perform full room mapping. Keep cane or guide aids active.</p>
          </div>
        </div>

        <div className="profile">
          <div className="avatar">ESM</div>
          <div>
            <strong>Spatial Suite</strong>
            <small>{isDemoMode ? "Virtual Simulation" : "Hardware Lab"}</small>
          </div>
          <ChevronDown size={14} />
        </div>
      </aside>

      {/* Main Workspace Area */}
      <section className="main-area">
        {/* Topbar */}
        <header className="topbar">
          <div className="breadcrumb">
            <span>ESM System</span>
            <span className="crumb-slash">/</span>
            <strong>{isDemoMode ? "Deterministic Demo Walkthrough" : "Live Hardware Workspace"}</strong>
          </div>
          <div className="top-actions">
            <button
              className={`demo-pill ${isDemoMode ? "demo-active-pill" : ""}`}
              onClick={toggleDemoMode}
              title="Toggle between hardware capture and deterministic offline demo"
            >
              <span /> {isDemoMode ? "DEMO MODE (ACTIVE)" : "HARDWARE MODE"}
            </button>
            <button
              className="icon-btn"
              aria-label="Toggle spoken audio alerts"
              onClick={() => setAudioAlertsEnabled(!audioAlertsEnabled)}
              title={audioAlertsEnabled ? "Audio proximity alerts ON" : "Audio proximity alerts OFF"}
            >
              {audioAlertsEnabled ? <Volume2 size={17} color="#00D1E8" /> : <VolumeX size={17} />}
            </button>
            <button className="icon-btn" aria-label="Toggle preferences" onClick={() => setShowSettings(!showSettings)}>
              <Settings2 size={17} />
            </button>
            <button className="avatar small" aria-label="Workspace menu">ESM</button>
          </div>
        </header>

        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow"><Sparkles size={12} /> IEEE-INSPIRED SPATIAL AWARENESS PLATFORM</div>
              <h1>ESM — Spatial Awareness System</h1>
              <p>Rigged 3D wearer origin, forward camera perception, real 3D environmental assets, and persistent sensor telemetry.</p>
            </div>
            <div className="heading-actions">
              <button className="button secondary" onClick={() => exportSession()}><Download size={15} /> Export JSON</button>
              <button className="button primary" onClick={saveSession}><Bookmark size={15} /> Save Session</button>
            </div>
          </div>

          {/* Status Banner */}
          <div className={`status-banner ${isDemoMode ? "demo-active-banner" : ""}`}>
            <div className="status-icon"><Radio size={18} /></div>
            <div className="status-copy">
              <strong>
                {isDemoMode
                  ? "Deterministic Simulation Engine Active"
                  : serial.status === "connected"
                  ? isDataStale
                    ? "Warning: Sensor telemetry is stale (> 2s without sample)"
                    : "ESP32 Connected — Live Hardware Stream"
                  : serial.status === "connecting"
                  ? "Waiting for serial port selection…"
                  : "Waiting for ESP32 Hardware (or click Demo Mode above)"}
              </strong>
              <span>
                {isDemoMode
                  ? "Virtual obstacles, rigged avatar, and sweep generated deterministically. Backend WS: " + backendStatus
                  : serial.lastError || (notice + " · Backend WS: " + backendStatus)}
              </span>
            </div>
            <div className="status-right">
              <span className="live-dot" />
              {isDemoMode ? "SIMULATING" : serial.status === "connected" ? "CONNECTED" : "STANDBY"}
              {!isDemoMode && (
                connected ? (
                  <button
                    className="text-button"
                    onClick={async () => {
                      await serial.disconnect();
                      setConnected(false);
                      setNotice("USB device disconnected.");
                    }}
                  >
                    <Usb size={14} /> Disconnect
                  </button>
                ) : (
                  <button
                    className="text-button"
                    onClick={async () => {
                      await serial.connect();
                    }}
                  >
                    <Usb size={14} /> Connect ESP32
                  </button>
                )
              )}
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="metrics-grid">
            <article className="metric-card">
              <div className="metric-top"><span>Nearest Range</span><span className="metric-icon blue"><Target size={16} /></span></div>
              <div className="metric-value">{shownDistance.toFixed(1)}<small>cm</small></div>
              <div className="metric-foot"><span className="live-dot" /> {isDataStale ? "Stale telemetry" : "Sampled just now"}</div>
            </article>

            <article className="metric-card">
              <div className="metric-top"><span>Proximity Alert</span><span className="metric-icon violet"><Activity size={16} /></span></div>
              <div className="metric-value">{band}<small className="band-dot" /></div>
              <div className="proximity-track"><span style={{ width: `${proximityWidth}%` }} /></div>
              <div className="metric-foot">Alert threshold · {threshold} cm {audioAlertsEnabled && "· Speech ON"}</div>
            </article>

            <article className="metric-card">
              <div className="metric-top"><span>Spatial Points</span><span className="metric-icon mint"><Grid2X2 size={16} /></span></div>
              <div className="metric-value">{sampleCount.toLocaleString()}<small>pts</small></div>
              <div className="metric-foot"><Activity size={12} /> {scanning && !paused ? "Recording in progress" : "Ready to scan"}</div>
            </article>

            <article className="metric-card">
              <div className="metric-top"><span>Telemetry Rate</span><span className="metric-icon amber"><Gauge size={16} /></span></div>
              <div className="metric-value">{scanning && !paused ? "4.0 Hz" : "Idle"}<small className="stream-dot" /></div>
              <div className="metric-foot"><span className="live-dot" /> Updated {formattedNow}</div>
            </article>
          </div>

          {/* Sensor Diagnostics Strip */}
          <div className="imu-strip">
            <div><span>RELATIVE YAW (DRIFT PRONE)</span><strong>{(mapper.orientation.yaw * 180 / Math.PI).toFixed(1)}°</strong></div>
            <div><span>TILT PITCH / ROLL</span><strong>{(mapper.orientation.pitch * 180 / Math.PI).toFixed(1)}° / {(mapper.orientation.roll * 180 / Math.PI).toFixed(1)}°</strong></div>
            <div><span>ACCEPTED / REJECTED SAMPLES</span><strong>{mapper.accepted} / {mapper.rejected}</strong></div>
            <div><span>SAMPLE PIPELINE STATUS</span><strong>{lastSampleNote}</strong></div>
          </div>

          {/* 3D Scene (Region C) & Camera (Region B) Grid */}
          <div className="work-grid">
            {/* REGION C: Human-Centric Spatial View */}
            <section className="panel viewer-panel" ref={viewerContainerRef}>
              <div className="panel-header">
                <div>
                  <div className="panel-title">
                    <span className="title-icon"><Focus size={16} /></span>
                    <h2>3D Spatial Environment & Rigged Wearer Avatar</h2>
                    <span className="tag">RELATIVE FRAME</span>
                  </div>
                  <p>Rigged human origin (0,0,0) + forward directional cone + 3D contextual assets + ultrasonic points</p>
                </div>
                <div className="panel-tools">
                  <button className={`view-toggle ${viewMode === "3d" ? "selected" : ""}`} onClick={() => setViewMode("3d")} title="Perspective 3D View"><Layers3 size={13} /> 3D</button>
                  <button className={`view-toggle ${viewMode === "top" ? "selected" : ""}`} onClick={() => setViewMode("top")} title="Top-down Ortho View"><Eye size={13} /> Top</button>
                  <button className={`view-toggle ${viewMode === "front" ? "selected" : ""}`} onClick={() => setViewMode("front")} title="Front Elevation View"><Target size={13} /> Front</button>
                  <button className="icon-btn" aria-label="Reset scan view" onClick={() => setViewMode("3d")} title="Reset view"><RotateCcw size={15} /></button>
                  <button className="icon-btn" aria-label="Toggle fullscreen" onClick={toggleFullscreen} title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}>
                    <Maximize2 size={15} />
                  </button>
                </div>
              </div>

              {/* Layer Visibility Controls */}
              <div style={{ display: "flex", gap: "10px", padding: "6px 14px", background: "var(--panel-raised)", borderBottom: "1px solid var(--line-subtle)", fontSize: "10px" }}>
                <span style={{ color: "var(--text-muted)" }}>Layers:</span>
                <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer", color: showPointCloud ? "var(--teal)" : "var(--text-muted)" }}>
                  <input type="checkbox" checked={showPointCloud} onChange={(e) => setShowPointCloud(e.target.checked)} /> Point Cloud
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer", color: showLandmarks ? "var(--vision-purple)" : "var(--text-muted)" }}>
                  <input type="checkbox" checked={showLandmarks} onChange={(e) => setShowLandmarks(e.target.checked)} /> Persistent Landmarks
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer", color: showTrajectory ? "var(--telemetry-cyan)" : "var(--text-muted)" }}>
                  <input type="checkbox" checked={showTrajectory} onChange={(e) => setShowTrajectory(e.target.checked)} /> Trajectory
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer", color: showIllustrative ? "var(--text-secondary)" : "var(--text-muted)" }}>
                  <input type="checkbox" checked={showIllustrative} onChange={(e) => setShowIllustrative(e.target.checked)} /> Illustrative 3D Assets
                </label>
              </div>

              <div className="viewer-wrap">
                <ScanViewer
                  points={points}
                  landmarks={persistentLandmarks}
                  trajectory={cameraTrajectory}
                  viewMode={viewMode}
                  reducedMotion={reducedMotion}
                  wearerYaw={mapper.orientation.yaw}
                  wearerPitch={mapper.orientation.pitch}
                  isDemoMode={isDemoMode}
                  showPointCloud={showPointCloud}
                  showLandmarks={showLandmarks}
                  showTrajectory={showTrajectory}
                  showIllustrative={showIllustrative}
                  isLive={(scanning && !paused) || (connected && !isDataStale)}
                />
                <div className="viewer-badge">
                  <span className="live-dot" /> {isReplaying ? `REPLAYING (${replayProgress}/${replayEventTotal})` : scanning && !paused ? "RECORDING SCENE" : "VIEWPORT ACTIVE"} <span className="badge-divider" /> {points.length} points
                  {isReplaying && (
                    <button
                      onClick={stopReplay}
                      style={{
                        marginLeft: "10px",
                        background: "rgba(239, 68, 68, 0.2)",
                        border: "1px solid #ef4444",
                        color: "#ef4444",
                        borderRadius: "4px",
                        padding: "2px 6px",
                        fontSize: "10px",
                        cursor: "pointer"
                      }}
                    >
                      Stop Replay
                    </button>
                  )}
                </div>
                <div className="viewer-scale"><span>0 m</span><span>2 m</span><span>4 m</span><span>6 m</span></div>
                <div className="viewer-hint"><span>DRAG TO ORBIT</span><span>SCROLL TO ZOOM</span></div>
              </div>

              {/* Data Provenance Legend */}
              <div className="viewer-footer">
                <div className="legend">
                  <span className="legend-dot near" /><span>Measured (&lt;1.5m)</span>
                  <span className="legend-dot mid" /><span>Measured (1.5-3m)</span>
                  <span className="legend-dot far" /><span>Measured (&gt;3m)</span>
                  <span style={{ display: "inline-block", width: "8px", height: "8px", border: "1px solid #B066FE", marginLeft: "10px", borderRadius: "2px" }} />
                  <span style={{ color: "#B066FE" }}>Estimated (Vision)</span>
                  <span style={{ display: "inline-block", width: "8px", height: "8px", background: "#13263A", border: "1px solid #263B50", marginLeft: "10px" }} />
                  <span style={{ color: "#9FB1C5" }}>Illustrative (Context 3D Assets)</span>
                </div>
                <span className="coordinate-label">WEARER-CENTRIC +X RIGHT, +Y UP, -Z FORWARD</span>
              </div>
            </section>

            {/* Right Column: REGION B (Camera) & REGION D (Harmonic Proximity) */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              {/* REGION B: Forward Camera Panel */}
              <CameraPanel
                enabled={cameraEnabled}
                onToggle={() => setCameraEnabled(!cameraEnabled)}
                detections={visionDetections}
                demoMode={isDemoMode}
                visionStatus={visionStatus}
                onFrameCapture={(blob) => {
                  if (wsClientRef.current && !isDemoMode) {
                    const frameId = Math.floor(performance.now());
                    const ts = Date.now();
                    wsClientRef.current.sendBinaryFrame(frameId, ts, blob);
                  }
                }}
                onUpdateVisionConfig={(conf, iou) => {
                  wsClientRef.current?.updateVisionConfig(conf, iou);
                }}
              />

              {/* REGION D: Harmonic Proximity Radar */}
              <section className="panel feedback-panel" style={{ flex: 1 }}>
                <div className="panel-header">
                  <div>
                    <div className="panel-title"><span className="title-icon pulse-icon"><AudioLines size={16} /></span><h2>Harmonic Proximity</h2></div>
                    <p>Sensory radar & spoken speech warning</p>
                  </div>
                  <span className="tag">{audioAlertsEnabled ? "SPEECH ON" : "VISUAL"}</span>
                </div>
                <div className={`harmonic-stage ${band.toLowerCase()}`}>
                  <div className="harmonic-orbit orbit-a" />
                  <div className="harmonic-orbit orbit-b" />
                  <div className="harmonic-orbit orbit-c" />
                  <div className="harmonic-core">
                    <Waves size={28} />
                    <span>{Math.round(shownDistance)}<small>cm</small></span>
                  </div>
                  <div className="harmonic-caption">{band.toUpperCase()} PROXIMITY</div>
                </div>
                <div className="feedback-readout">
                  <div><span className="readout-label">Alert State</span><strong>{band} Range</strong></div>
                  <div className="readout-right"><span className="readout-label">Measured Distance</span><strong>{shownDistance.toFixed(1)} cm</strong></div>
                </div>
                <div className="threshold-row">
                  <span>Proximity Warning Threshold</span>
                  <strong>{threshold} cm</strong>
                </div>
                <input
                  aria-label="Proximity warning threshold"
                  type="range"
                  min="20"
                  max="120"
                  step="5"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                />
              </section>
            </div>
          </div>

          {/* Lower Grid: REGION D (Controls & Sessions) */}
          <div className="lower-grid">
            <section className="panel controls-panel">
              <div className="panel-header">
                <div>
                  <div className="panel-title"><span className="title-icon"><SlidersHorizontal size={16} /></span><h2>Scan & Pose Controls</h2></div>
                  <p>Control recording state and coordinate calibration</p>
                </div>
                <span className="tag">
                  {scanning && !paused ? "RECORDING" : paused ? "PAUSED" : "STANDBY"}
                </span>
              </div>
              <div className="control-buttons">
                <button
                  className="button secondary"
                  disabled={(!connected && !isDemoMode) || scanning}
                  onClick={() => {
                    mapperRef.current = initialMapperState();
                    setMapper(mapperRef.current);
                    setNotice("Relative orientation zeroed. Keep sensor level and steady before moving.");
                  }}
                >
                  <Target size={14} /> Zero Relative Pose
                </button>
                <button
                  className="button secondary"
                  onClick={async () => {
                    setPoints([]);
                    setPersistentLandmarks([]);
                    setSampleCount(0);
                    mapperRef.current = initialMapperState();
                    setMapper(mapperRef.current);

                    // Reset map on backend as well without deleting stored session data
                    if (activeBackendSessionId) {
                      try {
                        await fetch(`http://localhost:8000/api/v1/sessions/${activeBackendSessionId}/map/reset`, {
                          method: "POST"
                        });
                      } catch {}
                    }
                    if (wsClientRef.current) {
                      // Also send map.reset event over WebSocket
                      (wsClientRef.current as any).ws?.send?.(JSON.stringify({ event: "map.reset" }));
                    }
                    setNotice("Spatial points and in-memory map reset. Session data preserved in database.");
                  }}
                >
                  <RotateCcw size={14} /> Reset Map
                </button>
              </div>
              <p className="calibration-note">
                Calibration zeroes relative orientation. Note: MPU6050 lacks a magnetometer; yaw drifts over time.
              </p>
              <label className="field-label" htmlFor="scan-name">SESSION NAME</label>
              <input
                id="scan-name"
                className="text-input"
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
                placeholder="Name this exploration session"
              />
              <div className="control-buttons">
                <button
                  className="button primary grow"
                  onClick={() => {
                    if (!connected && !isDemoMode) {
                      setNotice("Connect ESP32 or switch to Demo Mode above to record spatial points.");
                      return;
                    }
                    if (!scanning) {
                      setScanning(true);
                      scanningRef.current = true;
                      setPaused(false);
                      pausedRef.current = false;
                      setNotice(isDemoMode ? "Recording deterministic demo scan." : "Recording real sensor points into local relative frame.");
                    } else if (paused) {
                      setPaused(false);
                      pausedRef.current = false;
                    }
                  }}
                >
                  <Play size={15} /> {!scanning ? "Start Scan" : paused ? "Resume Scan" : "Scanning…"}
                </button>
                <button
                  className="button secondary"
                  disabled={!scanning || paused}
                  onClick={() => {
                    setPaused(true);
                    pausedRef.current = true;
                  }}
                >
                  <Pause size={15} /> Pause
                </button>
                <button
                  className="button secondary square"
                  aria-label="Clear scan"
                  onClick={() => {
                    setScanning(false);
                    scanningRef.current = false;
                    setPaused(false);
                    pausedRef.current = false;
                    setPoints([]);
                    setSampleCount(0);
                    setNotice("Current scan cleared.");
                  }}
                >
                  <RotateCcw size={15} />
                </button>
              </div>
              <div className="control-meta">
                <span><Timer size={14} /> Mode: {isDemoMode ? "Deterministic Demo" : "Hardware Serial"}</span>
                <span><span className="live-dot" /> {points.length} points recorded</span>
              </div>
            </section>

            {/* Saved Environments */}
            <section className="panel sessions-panel" id="sessions">
              <div className="panel-header">
                <div>
                  <div className="panel-title"><span className="title-icon"><Layers3 size={16} /></span><h2>Saved Environments</h2></div>
                  <p>Local and backend persisted sessions</p>
                </div>
                <span className="nav-count">{sessions.length} saved</span>
              </div>
              {sessions.length === 0 ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--text-muted)" }}>
                  <Scan size={24} style={{ margin: "0 auto 8px" }} />
                  <strong style={{ display: "block", color: "var(--text-primary)" }}>No saved environments yet</strong>
                  <span>Save a scan to persist in your local library and backend database.</span>
                </div>
              ) : (
                <div className="session-list">
                  {sessions.slice(0, 4).map((session) => (
                    <div className="session-row" key={session.id}>
                      <div className="session-thumb"><Waves size={18} /></div>
                      <div className="session-info">
                        <strong>{session.name}</strong>
                        <span>{new Date(session.savedAt).toLocaleDateString()} · {session.sampleCount} points</span>
                      </div>
                      <button className="icon-btn" aria-label={`Replay ${session.name}`} onClick={() => replaySession(session)} title="Replay session in timestamp order" style={{ color: "var(--teal)" }}>
                        <Play size={15} />
                      </button>
                      <button className="icon-btn" aria-label={`Load ${session.name}`} onClick={() => loadSession(session)} title="Load into viewport">
                        <ArrowUpRight size={15} />
                      </button>
                      <button className="icon-btn" aria-label={`Export ${session.name}`} onClick={() => exportSession(session)} title="Export JSON">
                        <Download size={15} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="sessions-footer">
                <label className="button secondary import-button">
                  <FileUp size={14} /> Import JSON
                  <input type="file" accept="application/json,.json" hidden onChange={(e) => importSession(e.target.files?.[0])} />
                </label>
                <button className="text-button" onClick={() => exportSession()}>Export Current <ArrowDownRight size={13} /></button>
              </div>
            </section>
          </div>

          {/* Preferences Modal */}
          {showSettings && (
            <section className="panel settings-panel">
              <div className="panel-header">
                <div><div className="panel-title"><Settings2 size={16} /><h2>Preferences</h2></div><p>Configure telemetry and accessibility</p></div>
                <button className="icon-btn" aria-label="Close preferences" onClick={() => setShowSettings(false)}><X size={16} /></button>
              </div>
              <label className="setting-row">
                <span><strong>Reduced motion</strong><small>Disable animated CSS orbits and high-framerate updates</small></span>
                <input type="checkbox" checked={reducedMotion} onChange={(e) => setReducedMotion(e.target.checked)} />
              </label>
              <label className="setting-row">
                <span><strong>Spoken proximity warnings</strong><small>Use speech synthesis to announce obstacles under threshold</small></span>
                <input type="checkbox" checked={audioAlertsEnabled} onChange={(e) => setAudioAlertsEnabled(e.target.checked)} />
              </label>
            </section>
          )}

          {/* Sensor Diagnostics Modal View */}
          {activeNav === "diagnostics" && (
            <section className="panel settings-panel" style={{ marginTop: "16px" }}>
              <div className="panel-header">
                <div>
                  <div className="panel-title"><Cpu size={16} /><h2>Sensor Diagnostics & SLAM Engine Status</h2></div>
                  <p>Telemetry stream health, orientation drift analysis, and SLAM backend evaluation</p>
                </div>
                <button className="icon-btn" aria-label="Close diagnostics" onClick={() => setActiveNav("workspace")}><X size={16} /></button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", padding: "16px" }}>
                <div style={{ background: "var(--panel-raised)", padding: "14px", borderRadius: "6px" }}>
                  <h3 style={{ fontSize: "12px", color: "var(--telemetry-cyan)", marginBottom: "8px" }}>HARDWARE TELEMETRY</h3>
                  <div style={{ fontSize: "11px", display: "flex", flexDirection: "column", gap: "6px" }}>
                    <div>Status: <strong>{connected ? "CONNECTED (Web Serial @ 115200)" : isDemoMode ? "SIMULATOR ACTIVE" : "DISCONNECTED"}</strong></div>
                    <div>Distance: <strong>{hardwareDistance !== null ? `${hardwareDistance.toFixed(1)} cm` : "No echo"}</strong></div>
                    <div>Yaw (integrated): <strong>{(mapper.orientation.yaw * 180 / Math.PI).toFixed(2)}°</strong> (drift-prone, no compass)</div>
                    <div>Pitch / Roll: <strong>{(mapper.orientation.pitch * 180 / Math.PI).toFixed(2)}° / {(mapper.orientation.roll * 180 / Math.PI).toFixed(2)}°</strong></div>
                    <div>Accepted / Rejected: <strong>{mapper.accepted} / {mapper.rejected}</strong> samples</div>
                    <div>Serial Port Buffer: <strong>{serial.validCount} valid / {serial.invalidCount} malformed</strong></div>
                  </div>
                </div>
                <div style={{ background: "var(--panel-raised)", padding: "14px", borderRadius: "6px" }}>
                  <h3 style={{ fontSize: "12px", color: "var(--vision-purple)", marginBottom: "8px" }}>SLAM & MAPPING BACKEND</h3>
                  <div style={{ fontSize: "11px", display: "flex", flexDirection: "column", gap: "6px" }}>
                    <div>SLAM Engine: <strong>{slamStatus?.engine_name || "none"}</strong></div>
                    <div>SLAM State: <strong style={{ color: "var(--warning-amber)" }}>{slamStatus?.state ? slamStatus.state.toUpperCase() : "UNAVAILABLE"}</strong></div>
                    <div>Evaluation: <span>ORB-SLAM3 evaluated; native C++ build required. Interface tested.</span></div>
                    <div>Metric Scale Source: <strong>{isDemoMode ? "Synthetic fixed metric" : "HC-SR04 ultrasonic echo (forward-only)"}</strong></div>
                    <div>Persistent Landmarks: <strong>{persistentLandmarks.length}</strong> ({persistentLandmarks.filter(l => !l.is_stale).length} active)</div>
                    <div>Backend WebSocket: <strong>{backendStatus.toUpperCase()}</strong></div>
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* 3D Asset Library Modal View */}
          {activeNav === "library" && (
            <section className="panel settings-panel" style={{ marginTop: "16px" }}>
              <div className="panel-header">
                <div>
                  <div className="panel-title"><Box size={16} /><h2>Local 3D Asset Library</h2></div>
                  <p>Bundled CC0/permissive local GLTF assets rendered in the spatial viewer (see docs/ASSET_CREDITS.md)</p>
                </div>
                <button className="icon-btn" aria-label="Close asset library" onClick={() => setActiveNav("workspace")}><X size={16} /></button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "12px", padding: "16px" }}>
                {[
                  { name: "Wearer Avatar", path: "/assets/3d/human/wearer_avatar.glb", category: "Human", prov: "Illustrative" },
                  { name: "Office Table", path: "/assets/3d/indoor/office_table.glb", category: "Indoor", prov: "Illustrative" },
                  { name: "Office Chair", path: "/assets/3d/indoor/office_chair.glb", category: "Indoor", prov: "Illustrative" },
                  { name: "Storage Cabinet", path: "/assets/3d/indoor/cabinet.glb", category: "Indoor", prov: "Illustrative" },
                  { name: "Wall Partition", path: "/assets/3d/environment/wall_partition.glb", category: "Structure", prov: "Illustrative" },
                  { name: "Door Frame", path: "/assets/3d/environment/door_frame.glb", category: "Structure", prov: "Illustrative" },
                  { name: "Traffic Bollard", path: "/assets/3d/street/traffic_bollard.glb", category: "Street", prov: "Illustrative" },
                  { name: "Park Bench", path: "/assets/3d/street/park_bench.glb", category: "Street", prov: "Illustrative" },
                  { name: "Pedestrian (Demo)", path: "/assets/3d/outdoor/pedestrian.glb", category: "Outdoor", prov: "Illustrative (Demo)" },
                ].map((asset) => (
                  <div key={asset.name} style={{ background: "var(--panel-raised)", padding: "10px", borderRadius: "6px", border: "1px solid var(--line-subtle)" }}>
                    <div style={{ fontSize: "11px", fontWeight: "bold", color: "var(--text-primary)" }}>{asset.name}</div>
                    <div style={{ fontSize: "9px", color: "var(--telemetry-cyan)", marginTop: "2px" }}>{asset.category} · {asset.prov}</div>
                    <div style={{ fontSize: "8px", color: "var(--text-muted)", marginTop: "4px", overflow: "hidden", textOverflow: "ellipsis" }}>{asset.path}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <footer className="footer">
            <span>ESM — SPATIAL AWARENESS SYSTEM · V1.0.0</span>
            <span><ShieldCheck size={13} /> Assistive research prototype · Not for autonomous navigation</span>
          </footer>
        </div>
      </section>
    </main>
  );
}
