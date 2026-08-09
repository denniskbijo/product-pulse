"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_DURATION_MS = 3000;

export function useToast(durationMs = DEFAULT_DURATION_MS) {
  const [toast, setToast] = useState<{ id: number; message: string } | null>(
    null,
  );

  const showToast = useCallback((message: string) => {
    setToast({ id: Date.now(), message });
  }, []);

  const dismissToast = useCallback(() => setToast(null), []);

  return {
    toast,
    showToast,
    dismissToast,
    durationMs,
  };
}

export function Toast({
  message,
  toastKey,
  onClose,
  durationMs = DEFAULT_DURATION_MS,
}: {
  message: string;
  toastKey: number;
  onClose: () => void;
  durationMs?: number;
}) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const remainingRef = useRef(durationMs);
  const startedAtRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    remainingRef.current = durationMs;
    setPaused(false);

    const clear = () => {
      if (timerRef.current != null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };

    startedAtRef.current = Date.now();
    timerRef.current = setTimeout(() => {
      onCloseRef.current();
    }, remainingRef.current);

    return clear;
  }, [toastKey, durationMs]);

  const onMouseEnter = () => {
    setPaused(true);
    if (timerRef.current != null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (startedAtRef.current != null) {
      const elapsed = Date.now() - startedAtRef.current;
      remainingRef.current = Math.max(0, remainingRef.current - elapsed);
      startedAtRef.current = null;
    }
  };

  const onMouseLeave = () => {
    setPaused(false);
    if (remainingRef.current <= 0) {
      onCloseRef.current();
      return;
    }
    startedAtRef.current = Date.now();
    timerRef.current = setTimeout(() => {
      onCloseRef.current();
    }, remainingRef.current);
  };

  return (
    <div className="toast-viewport" aria-live="polite">
      <div
        className={`toast${paused ? " toast-paused" : ""}`}
        role="status"
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
      >
        <p className="toast-message">{message}</p>
        <button
          type="button"
          className="toast-close"
          aria-label="Dismiss notification"
          onClick={() => onCloseRef.current()}
        >
          ×
        </button>
      </div>
    </div>
  );
}
