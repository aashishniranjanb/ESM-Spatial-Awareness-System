import type { SensorMessage } from "@/lib/serial/protocol";
import type { ScanPoint, VisionOverlay } from "@/components/scan-viewer";

export type VisionDetectionPayload = {
  id: string;
  class_name: string;
  class_id: number;
  confidence: number;
  box_normalized: { x: number; y: number; w: number; h: number };
  track_id?: number;
  overlaps_path_corridor: boolean;
  corridor_overlap_ratio: number;
  is_path_obstruction: boolean;
  is_approximate: boolean;
  uncertainty: number;
  latency_ms?: number;
  acoustic_candidate_dist_m?: number;
};

export type VisionStatusPayload = {
  model_name: string;
  model_ready: boolean;
  device: string;
  input_size: number;
  confidence_threshold: number;
  iou_threshold: number;
  tracking_enabled: boolean;
  processed_fps: number;
  avg_latency_ms: number;
};

export type SLAMStatusPayload = {
  state: string;
  engine_name: string;
  available: boolean;
  message?: string;
};

export type LandmarkPayload = {
  id: string;
  x: number;
  y: number;
  z: number;
  label?: string;
  confidence: number;
  observation_count: number;
  uncertainty: number;
  provenance: "measured" | "estimated" | "illustrative";
  source: string;
  track_id?: number;
  is_stale: boolean;
  has_valid_depth: boolean;
  depth_source?: string;
};

export type MapUpdatePayload = {
  landmarks: LandmarkPayload[];
  active_tracks: any[];
  map_status: {
    session_id: string;
    total_landmarks: number;
    active_landmarks: number;
    stale_landmarks: number;
    total_object_tracks: number;
    active_object_tracks: number;
    camera_pose_count: number;
    current_frame_id: number;
  };
};

export class BackendWSClient {
  private ws: WebSocket | null = null;
  private url: string;
  private sessionId: string;
  private reconnectTimer: any = null;
  private heartbeatTimer: any = null;
  private reconnectAttempts = 0;
  private isExplicitlyClosed = false;
  
  private onPointCallback?: (p: ScanPoint) => void;
  private onStatusCallback?: (status: "connected" | "disconnected" | "error") => void;
  private onVisionCallback?: (detections: VisionDetectionPayload[], latency_ms: number) => void;
  private onVisionStatusCallback?: (status: VisionStatusPayload) => void;
  private onSLAMStatusCallback?: (status: SLAMStatusPayload) => void;
  private onMapUpdateCallback?: (mapData: MapUpdatePayload) => void;

  constructor(sessionId: string = "global", url: string = "ws://localhost:8000/ws") {
    this.sessionId = sessionId;
    this.url = `${url}/${sessionId}`;
  }

  public setCallbacks(
    onPoint?: (p: ScanPoint) => void,
    onStatus?: (status: "connected" | "disconnected" | "error") => void,
    onVision?: (detections: VisionDetectionPayload[], latency_ms: number) => void,
    onVisionStatus?: (status: VisionStatusPayload) => void,
    onSLAMStatus?: (status: SLAMStatusPayload) => void,
    onMapUpdate?: (mapData: MapUpdatePayload) => void
  ) {
    this.onPointCallback = onPoint;
    this.onStatusCallback = onStatus;
    this.onVisionCallback = onVision;
    this.onVisionStatusCallback = onVisionStatus;
    this.onSLAMStatusCallback = onSLAMStatus;
    this.onMapUpdateCallback = onMapUpdate;
  }

  public connect() {
    this.isExplicitlyClosed = false;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.onStatusCallback?.("connected");
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === "spatial.point" && this.onPointCallback) {
            this.onPointCallback(data.payload);
          } else if (data.event === "vision.detection" && this.onVisionCallback) {
            this.onVisionCallback(data.payload.detections || [], data.payload.latency_ms || 0);
            if (data.payload.status && this.onVisionStatusCallback) {
              this.onVisionStatusCallback(data.payload.status);
            }
          } else if (data.event === "vision.status" && this.onVisionStatusCallback) {
            this.onVisionStatusCallback(data.payload);
          } else if (data.event === "slam.status" && this.onSLAMStatusCallback) {
            this.onSLAMStatusCallback(data.payload);
          } else if (data.event === "map.update" && this.onMapUpdateCallback) {
            this.onMapUpdateCallback(data.payload);
          }
        } catch {}
      };

      this.ws.onerror = () => {
        this.onStatusCallback?.("error");
      };

      this.ws.onclose = () => {
        this.stopHeartbeat();
        this.onStatusCallback?.("disconnected");
        if (!this.isExplicitlyClosed) {
          clearTimeout(this.reconnectTimer);
          // Exponential backoff with jitter: min 1.5s, max 15s
          this.reconnectAttempts++;
          const baseDelay = Math.min(15000, 1500 * Math.pow(1.5, Math.min(this.reconnectAttempts, 6)));
          const jitter = Math.random() * 500;
          this.reconnectTimer = setTimeout(() => this.connect(), baseDelay + jitter);
        }
      };
    } catch {
      this.onStatusCallback?.("error");
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ event: "ping", timestamp: Date.now() }));
      }
    }, 15000);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  public forwardSample(sample: SensorMessage) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          event: "sensor.sample",
          session_id: this.sessionId,
          payload: sample,
        })
      );
    }
  }

  public sendBinaryFrame(frameId: number, timestampMs: number, jpegBlob: Blob) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      jpegBlob.arrayBuffer().then((buffer) => {
        // Construct binary packet: 8 bytes header (4B frameId, 4B timestampMs) + raw image
        const header = new ArrayBuffer(8);
        const view = new DataView(header);
        view.setUint32(0, frameId, true);
        view.setUint32(4, timestampMs, true);

        const packet = new Uint8Array(8 + buffer.byteLength);
        packet.set(new Uint8Array(header), 0);
        packet.set(new Uint8Array(buffer), 8);

        this.ws?.send(packet);
      });
    }
  }

  public updateVisionConfig(conf: number, iou: number, corridor?: { x_min: number; x_max: number; y_min: number; y_max: number }) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          event: "vision.config",
          session_id: this.sessionId,
          payload: {
            conf_thresh: conf,
            iou_thresh: iou,
            corridor,
          },
        })
      );
    }
  }

  public disconnect() {
    this.isExplicitlyClosed = true;
    this.stopHeartbeat();
    clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
