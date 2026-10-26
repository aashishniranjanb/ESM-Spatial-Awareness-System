"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { parseSensorLine, type SensorMessage, type SerialStatus } from "@/lib/serial/protocol";

type SerialPortLike = {
  open: (options: { baudRate: number }) => Promise<void>;
  close: () => Promise<void>;
  readable: ReadableStream<Uint8Array> | null;
  writable: WritableStream<Uint8Array> | null;
};
type SerialNavigator = Navigator & {
  serial?: {
    requestPort: () => Promise<SerialPortLike>;
  };
};

export function useSerialDevice(onSample: (sample: SensorMessage) => void) {
  const [status, setStatus] = useState<SerialStatus>("disconnected");
  const [lastError, setLastError] = useState("");
  const [validCount, setValidCount] = useState(0);
  const [invalidCount, setInvalidCount] = useState(0);
  const portRef = useRef<SerialPortLike | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const aliveRef = useRef(false);
  const decoderRef = useRef(new TextDecoder());
  const onSampleRef = useRef(onSample);
  useEffect(() => { onSampleRef.current = onSample; }, [onSample]);

  const supported = typeof navigator !== "undefined" && "serial" in navigator;

  const disconnect = useCallback(async () => {
    aliveRef.current = false;
    try { await readerRef.current?.cancel(); } catch {}
    try { readerRef.current?.releaseLock(); } catch {}
    readerRef.current = null;
    try { await portRef.current?.close(); } catch {}
    portRef.current = null;
    setStatus("disconnected");
  }, []);

  const connect = useCallback(async () => {
    const serial = (navigator as SerialNavigator).serial;
    if (!serial) {
      setStatus("unsupported");
      setLastError("Web Serial is unavailable. Use a supported Chromium desktop browser over HTTPS or localhost.");
      return;
    }
    try {
      setStatus("connecting");
      setLastError("");
      const port = await serial.requestPort();
      await port.open({ baudRate: 115200 });
      portRef.current = port;
      if (!port.readable) throw new Error("The selected serial port has no readable stream.");
      const reader = port.readable.getReader();
      readerRef.current = reader;
      aliveRef.current = true;
      setStatus("connected");
      let buffer = "";
      while (aliveRef.current) {
        const { value, done } = await reader.read();
        if (done) break;
        if (!value) continue;
        buffer += decoderRef.current.decode(value, { stream: true });
        if (buffer.length > 32768) {
          buffer = buffer.slice(-8192);
          setInvalidCount((n) => n + 1);
        }
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          try {
            const sample = parseSensorLine(trimmed);
            onSampleRef.current(sample);
            setValidCount((n) => n + 1);
          } catch (error) {
            setInvalidCount((n) => n + 1);
            setLastError(error instanceof Error ? error.message : "Invalid serial record");
          }
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Serial connection failed";
      setLastError(message);
      if (message.toLowerCase().includes("cancel")) setStatus("disconnected");
      else setStatus("error");
    } finally {
      aliveRef.current = false;
      try { readerRef.current?.releaseLock(); } catch {}
      readerRef.current = null;
      try { await portRef.current?.close(); } catch {}
      portRef.current = null;
      setStatus((s) => s === "error" || s === "unsupported" ? s : "disconnected");
    }
  }, []);

  useEffect(() => () => {
    aliveRef.current = false;
    try { readerRef.current?.cancel(); } catch {}
  }, []);

  return { status, supported, lastError, validCount, invalidCount, connect, disconnect };
}
