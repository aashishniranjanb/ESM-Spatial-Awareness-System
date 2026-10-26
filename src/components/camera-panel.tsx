"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Camera, CameraOff, AlertCircle, Eye, Maximize2, Minimize2, Video, Sliders, ShieldAlert, Cpu } from "lucide-react";
import type { VisionOverlay } from "@/components/scan-viewer";

export type ExtendedVisionOverlay = VisionOverlay & {
  class_name?: string;
  box_normalized?: { x: number; y: number; w: number; h: number };
  track_id?: number;
  overlaps_path_corridor?: boolean;
  corridor_overlap_ratio?: number;
  is_path_obstruction?: boolean;
  latency_ms?: number;
  uncertainty?: number;
  acoustic_candidate_dist_m?: number;
};

export default function CameraPanel({
  enabled,
  onToggle,
  detections = [],
  demoMode,
  onFrameCapture,
  visionStatus,
  onUpdateVisionConfig,
}: {
  enabled: boolean;
  onToggle: () => void;
  detections: ExtendedVisionOverlay[];
  demoMode: boolean;
  onFrameCapture?: (blob: Blob) => void;
  visionStatus?: {
    model_name: string;
    model_ready: boolean;
    device: string;
    processed_fps: number;
    avg_latency_ms: number;
  };
  onUpdateVisionConfig?: (conf: number, iou: number) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("");
  const [permissionError, setPermissionError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showVisionControls, setShowVisionControls] = useState(false);
  
  // Real-time camera telemetry
  const [fps, setFps] = useState<number>(0);
  const [lastFrameTime, setLastFrameTime] = useState<string>("--:--:--");
  const [confThresh, setConfThresh] = useState<number>(0.35);
  const [iouThresh, setIouThresh] = useState<number>(0.45);

  // Frame capture loop for backend YOLO inference (approx 8-10 FPS max)
  const frameCaptureIntervalRef = useRef<any>(null);

  const updateFrameStats = useCallback(() => {
    const d = new Date();
    setLastFrameTime(d.toTimeString().split(" ")[0] + "." + Math.floor(d.getMilliseconds() / 100));
  }, []);

  // Enumerate video devices when permissions allowed
  const enumerateCameras = async () => {
    try {
      const devList = await navigator.mediaDevices.enumerateDevices();
      const videoDevs = devList.filter((d) => d.kind === "videoinput");
      setDevices(videoDevs);
      if (videoDevs.length > 0 && !selectedDeviceId) {
        setSelectedDeviceId(videoDevs[0].deviceId);
      }
    } catch {}
  };

  useEffect(() => {
    let activeStream: MediaStream | null = null;
    if (enabled && !demoMode) {
      const constraints: MediaStreamConstraints = {
        video: selectedDeviceId
          ? { deviceId: { exact: selectedDeviceId }, width: { ideal: 640 }, height: { ideal: 480 } }
          : { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      };

      navigator.mediaDevices
        ?.getUserMedia(constraints)
        .then((s) => {
          activeStream = s;
          setStream(s);
          if (videoRef.current) {
            videoRef.current.srcObject = s;
          }
          setPermissionError(null);
          enumerateCameras();

          // Setup frame capture loop (every 120ms = ~8 FPS)
          clearInterval(frameCaptureIntervalRef.current);
          frameCaptureIntervalRef.current = setInterval(() => {
            if (videoRef.current && canvasRef.current && onFrameCapture) {
              const video = videoRef.current;
              const canvas = canvasRef.current;
              if (video.videoWidth > 0 && video.videoHeight > 0) {
                canvas.width = 320;
                canvas.height = 240;
                const ctx = canvas.getContext("2d");
                if (ctx) {
                  ctx.drawImage(video, 0, 0, 320, 240);
                  canvas.toBlob(
                    (blob) => {
                      if (blob) onFrameCapture(blob);
                    },
                    "image/jpeg",
                    0.65
                  );
                }
              }
            }
            updateFrameStats();
          }, 120);
        })
        .catch((err) => {
          setPermissionError(err.message || "Camera permission denied or camera not found.");
        });
    } else {
      clearInterval(frameCaptureIntervalRef.current);
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
        setStream(null);
      }
      if (videoRef.current) videoRef.current.srcObject = null;
      setFps(0);
    }

    return () => {
      clearInterval(frameCaptureIntervalRef.current);
      if (activeStream) {
        activeStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [enabled, demoMode, selectedDeviceId, onFrameCapture, updateFrameStats]);

  const handleConfidenceChange = (val: number) => {
    setConfThresh(val);
    onUpdateVisionConfig?.(val, iouThresh);
  };

  return (
    <div className={`camera-panel-container ${isExpanded ? "camera-expanded-mode" : ""}`}>
      {/* Hidden canvas for offscreen frame grab */}
      <canvas ref={canvasRef} style={{ display: "none" }} />

      <div className="camera-header">
        <div className="camera-title">
          <Camera size={14} />
          <span>FORWARD OPTICAL FEED</span>
          {enabled && !demoMode && (
            <span className="cam-badge-live">
              {visionStatus?.model_ready ? `YOLO (${visionStatus.processed_fps} FPS)` : "LIVE WEBCAM"}
            </span>
          )}
          {demoMode && <span className="cam-badge-demo">SYNTHETIC FEED</span>}
        </div>
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          {devices.length > 1 && enabled && !demoMode && (
            <select
              className="camera-device-select"
              value={selectedDeviceId}
              onChange={(e) => setSelectedDeviceId(e.target.value)}
              aria-label="Select camera source"
            >
              {devices.map((d, idx) => (
                <option key={d.deviceId || idx} value={d.deviceId}>
                  {d.label || `Camera ${idx + 1}`}
                </option>
              ))}
            </select>
          )}
          {enabled && (
            <>
              <button
                className={`icon-btn ${showVisionControls ? "active" : ""}`}
                style={{ width: "26px", height: "26px" }}
                onClick={() => setShowVisionControls(!showVisionControls)}
                aria-label="Toggle vision threshold controls"
                title="Vision threshold controls"
              >
                <Sliders size={13} />
              </button>
              <button
                className="icon-btn"
                style={{ width: "26px", height: "26px" }}
                onClick={() => setIsExpanded(!isExpanded)}
                aria-label={isExpanded ? "Collapse camera view" : "Expand camera view"}
                title={isExpanded ? "Collapse camera view" : "Expand camera view"}
              >
                {isExpanded ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
              </button>
            </>
          )}
          <button className="text-button-cam" onClick={onToggle}>
            {enabled ? (
              <>
                <CameraOff size={12} /> Disable
              </>
            ) : (
              <>
                <Camera size={12} /> Enable Camera
              </>
            )}
          </button>
        </div>
      </div>

      {/* Vision Threshold Drawer */}
      {showVisionControls && (
        <div
          style={{
            padding: "8px 14px",
            background: "var(--panel-raised)",
            borderBottom: "1px solid var(--line)",
            display: "flex",
            gap: "14px",
            alignItems: "center",
            fontSize: "10px",
          }}
        >
          <div>
            <span>Conf: <strong>{Math.round(confThresh * 100)}%</strong></span>
            <input
              type="range"
              min="0.15"
              max="0.85"
              step="0.05"
              value={confThresh}
              onChange={(e) => handleConfidenceChange(parseFloat(e.target.value))}
              style={{ width: "80px", margin: "0 6px" }}
            />
          </div>
          <div>
            <span>Backend: <strong>{visionStatus?.device || "cpu"}</strong></span>
          </div>
          <div style={{ marginLeft: "auto", color: "var(--text-muted)" }}>
            Latency: <strong>{visionStatus?.avg_latency_ms || 0}ms</strong>
          </div>
        </div>
      )}

      <div className="camera-view" style={{ height: isExpanded ? "380px" : "220px" }}>
        {enabled ? (
          demoMode ? (
            <div className="synthetic-camera-view">
              <div className="synthetic-grid-overlay" />
              {/* Visual Forward Path Corridor (Normalized: x in [0.30, 0.70]) */}
              <div
                style={{
                  position: "absolute",
                  top: "35%",
                  bottom: "0%",
                  left: "30%",
                  width: "40%",
                  borderLeft: "1px dashed rgba(0, 209, 232, 0.45)",
                  borderRight: "1px dashed rgba(0, 209, 232, 0.45)",
                  background: "rgba(0, 209, 232, 0.04)",
                  pointerEvents: "none",
                }}
              >
                <div style={{ position: "absolute", bottom: "6px", left: "6px", font: "8px var(--mono)", color: "rgba(0, 209, 232, 0.6)" }}>
                  FORWARD PATH CORRIDOR
                </div>
              </div>
              <div className="synthetic-wearer-view">
                <div className="crosshair" />
                <span className="demo-view-caption">SYNTHETIC VIRTUAL SCENARIO (DEMO MODE)</span>
              </div>
              {/* Demo Mode Bounding Box Overlays */}
              {detections.map((det) => (
                <div
                  key={det.id}
                  className="vision-box-overlay"
                  style={{ top: "25%", left: "30%", width: "40%", height: "50%" }}
                >
                  <div className="vision-box-tag">
                    {det.label} ({Math.round(det.confidence * 100)}%) · ~{det.est_distance_m}m (synthetic)
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="video-wrapper">
              <video ref={videoRef} autoPlay playsInline muted className="live-video" />
              {/* Visual Forward Path Corridor (Image-space research guide) */}
              <div
                style={{
                  position: "absolute",
                  top: "35%",
                  bottom: "0%",
                  left: "30%",
                  width: "40%",
                  borderLeft: "1px dashed rgba(0, 209, 232, 0.5)",
                  borderRight: "1px dashed rgba(0, 209, 232, 0.5)",
                  background: "rgba(0, 209, 232, 0.05)",
                  pointerEvents: "none",
                }}
              >
                <div style={{ position: "absolute", bottom: "6px", left: "6px", font: "8px var(--mono)", color: "rgba(0, 209, 232, 0.7)" }}>
                  VISUAL PATH CORRIDOR
                </div>
              </div>

              {/* Real-time YOLO Detection Overlays */}
              {detections.map((det) => {
                const box = det.box_normalized;
                if (!box) return null;
                const isObstruction = det.is_path_obstruction;
                const borderColor = isObstruction ? "var(--critical-red)" : det.overlaps_path_corridor ? "var(--warning-amber)" : "var(--vision-purple)";
                const tagBg = isObstruction ? "#5C121A" : det.overlaps_path_corridor ? "#4D3208" : "#3B1B68";

                return (
                  <div
                    key={det.id}
                    style={{
                      position: "absolute",
                      left: `${box.x * 100}%`,
                      top: `${box.y * 100}%`,
                      width: `${box.w * 100}%`,
                      height: `${box.h * 100}%`,
                      border: `2px solid ${borderColor}`,
                      boxShadow: `0 0 8px ${borderColor}66`,
                      borderRadius: "4px",
                      pointerEvents: "none",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        top: "-20px",
                        left: "-2px",
                        background: tagBg,
                        color: "#FFFFFF",
                        font: "8px var(--mono)",
                        padding: "2px 6px",
                        borderRadius: "3px",
                        whiteSpace: "nowrap",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      {det.track_id !== undefined && <span>#{det.track_id}</span>}
                      <strong>{det.label || det.class_name}</strong>
                      <span>{Math.round(det.confidence * 100)}%</span>
                      {det.acoustic_candidate_dist_m && (
                        <span style={{ color: "var(--telemetry-cyan)" }}>
                          · ~{det.acoustic_candidate_dist_m}m (echo est)
                        </span>
                      )}
                      {isObstruction && <span style={{ color: "var(--critical-red)" }}>[OBSTACLE]</span>}
                    </div>
                  </div>
                );
              })}

              {permissionError ? (
                <div className="camera-error">
                  <AlertCircle size={20} />
                  <span>{permissionError}</span>
                  <small>Please allow browser camera permissions in site settings.</small>
                </div>
              ) : (
                <div className="vision-status-tag">
                  <Eye size={12} />
                  <span>
                    {visionStatus?.model_ready
                      ? `YOLOv8 Active: ${detections.length} tracked obstacles`
                      : "Connecting to Python YOLO backend..."}
                  </span>
                </div>
              )}

              {/* Real-time frame statistics */}
              <div
                style={{
                  position: "absolute",
                  top: "8px",
                  right: "8px",
                  background: "rgba(7, 19, 33, 0.8)",
                  padding: "3px 7px",
                  borderRadius: "4px",
                  font: "8px var(--mono)",
                  color: "var(--telemetry-cyan)",
                  border: "1px solid var(--line)",
                }}
              >
                {visionStatus?.processed_fps || 0} FPS · {visionStatus?.avg_latency_ms || 0}ms · {lastFrameTime}
              </div>
            </div>
          )
        ) : (
          <div className="camera-placeholder">
            <CameraOff size={28} />
            <p>Laptop Webcam Standby</p>
            <small>Click &quot;Enable Camera&quot; to inspect forward optical view with real YOLO inference</small>
          </div>
        )}
      </div>

      {/* Detected Obstacle List Summary */}
      {enabled && detections.length > 0 && (
        <div
          style={{
            padding: "8px 14px",
            background: "var(--panel)",
            borderTop: "1px solid var(--line-subtle)",
            maxHeight: "85px",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "4px",
          }}
        >
          <div style={{ font: "8px var(--mono)", color: "var(--text-muted)", letterSpacing: "0.8px" }}>
            DETECTED PATH ENTITIES ({detections.length})
          </div>
          {detections.map((d) => (
            <div
              key={d.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                font: "9px var(--mono)",
                color: d.is_path_obstruction ? "var(--critical-red)" : "var(--text-secondary)",
              }}
            >
              <span>
                {d.track_id ? `[#${d.track_id}] ` : ""}{d.label || d.class_name} ({Math.round(d.confidence * 100)}%)
              </span>
              <span>
                {d.is_path_obstruction
                  ? "PATH OBSTRUCTION"
                  : d.overlaps_path_corridor
                  ? "IN CORRIDOR"
                  : "PERIPHERAL"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
