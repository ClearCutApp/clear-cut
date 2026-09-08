import { useEffect, useRef, useState } from "react";
import { transcribeQuestion, type SpeechLanguage } from "../../api/client";

export type RecordingPhase = "idle" | "requesting" | "recording" | "transcribing";
export const MAX_AUDIO_BYTES = 8 * 1024 * 1024;
export const RECORDING_TYPES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4;codecs=mp4a.40.2", "audio/mp4"];
export function recordingMime(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  return RECORDING_TYPES.find(type => MediaRecorder.isTypeSupported(type)) ?? null;
}

export function useVoiceRecorder(projectId: string, onTranscript: (text: string) => void) {
  const [phase, setPhase] = useState<RecordingPhase>("idle");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const sequence = useRef(0);
  const alive = useRef(true);
  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const abort = useRef<AbortController | null>(null);
  const receive = useRef(onTranscript);
  receive.current = onTranscript;

  function release() {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
  }
  function cancel() {
    sequence.current += 1;
    abort.current?.abort();
    if (recorder.current?.state === "recording") recorder.current.stop();
    recorder.current = null;
    release();
    if (alive.current) { setPhase("idle"); setSeconds(0); }
  }
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; cancel(); };
  }, [projectId]);

  function stop() {
    if (recorder.current?.state === "recording") recorder.current.stop();
    release();
  }
  async function start(language: SpeechLanguage) {
    if (phase !== "idle") return;
    const mimeType = recordingMime();
    if (!mimeType || !navigator.mediaDevices?.getUserMedia) { setError("unsupported"); return; }
    const current = ++sequence.current;
    setError(null); setSeconds(0); setPhase("requesting");
    try {
      const microphone = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!alive.current || current !== sequence.current) { microphone.getTracks().forEach(track => track.stop()); return; }
      stream.current = microphone;
      const capture = new MediaRecorder(microphone, { mimeType });
      recorder.current = capture;
      const chunks: Blob[] = [];
      let size = 0;
      capture.ondataavailable = event => {
        if (current !== sequence.current) return;
        size += event.data.size;
        if (size > MAX_AUDIO_BYTES) { cancel(); setError("too-large"); return; }
        if (event.data.size) chunks.push(event.data);
      };
      capture.onerror = () => { if (current === sequence.current) { cancel(); setError("recording"); } };
      capture.onstop = () => {
        if (!alive.current || current !== sequence.current) return;
        release();
        const audio = new Blob(chunks, { type: capture.mimeType });
        if (!audio.size) { setPhase("idle"); setError("empty"); return; }
        setPhase("transcribing");
        const controller = new AbortController(); abort.current = controller;
        void transcribeQuestion(projectId, audio, language, controller.signal).then(result => {
          if (alive.current && current === sequence.current) { receive.current(result.text); setPhase("idle"); }
        }).catch(() => { if (alive.current && current === sequence.current) { setError("transcription"); setPhase("idle"); } });
      };
      capture.start(250);
      setPhase("recording");
      const started = Date.now();
      timer.current = setInterval(() => {
        const elapsed = Math.min(60, Math.floor((Date.now() - started) / 1000));
        setSeconds(elapsed);
        if (elapsed >= 60) stop();
      }, 250);
    } catch (failure) {
      if (current === sequence.current) release();
      if (alive.current && current === sequence.current) { setPhase("idle"); setError(failure instanceof DOMException && failure.name === "NotAllowedError" ? "denied" : "recording"); }
    }
  }
  return { phase, seconds, error, start, stop, cancel, supported: recordingMime() !== null && !!navigator.mediaDevices?.getUserMedia };
}
