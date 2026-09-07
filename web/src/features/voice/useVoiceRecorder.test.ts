import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { transcribeQuestion } from "../../api/client";
import { useVoiceRecorder } from "./useVoiceRecorder";

vi.mock("../../api/client", () => ({ transcribeQuestion: vi.fn() }));
class Recorder {
  static isTypeSupported(type: string) { return type === "audio/mp4"; }
  state = "inactive";
  mimeType = "audio/mp4";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  static current: Recorder;
  constructor() { Recorder.current = this; }
  start() { this.state = "recording"; }
  stop() { this.state = "inactive"; this.ondataavailable?.({ data: new Blob(["AAC"], { type: this.mimeType }) }); this.onstop?.(); }
}
const track = { stop: vi.fn() };
const microphone = { getTracks: () => [track] } as unknown as MediaStream;
const getUserMedia = vi.fn();
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("MediaRecorder", Recorder);
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
  getUserMedia.mockResolvedValue(microphone);
  vi.mocked(transcribeQuestion).mockResolvedValue({ text: "Can we use this mural?", language: "en-US" });
});
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

it("stops all tracks and returns transcription for review in the captured project", async () => {
  const receive = vi.fn();
  const { result } = renderHook(() => useVoiceRecorder("project-a", receive));
  await act(async () => { await result.current.start("en-US"); });
  expect(result.current.phase).toBe("recording");
  await act(async () => { result.current.stop(); });
  expect(track.stop).toHaveBeenCalled();
  expect(transcribeQuestion).toHaveBeenCalledWith("project-a", expect.objectContaining({ type: "audio/mp4" }), "en-US", expect.any(AbortSignal));
  expect(receive).toHaveBeenCalledWith("Can we use this mural?");
});

it("releases a late microphone permission grant after cancellation", async () => {
  let grant!: (stream: MediaStream) => void;
  getUserMedia.mockReturnValue(new Promise(resolve => { grant = resolve; }));
  const { result } = renderHook(() => useVoiceRecorder("p", vi.fn()));
  let started!: Promise<void>;
  act(() => { started = result.current.start("en-US"); });
  act(() => result.current.cancel());
  await act(async () => { grant(microphone); await started; });
  expect(track.stop).toHaveBeenCalled();
  expect(result.current.phase).toBe("idle");
  expect(transcribeQuestion).not.toHaveBeenCalled();
});

it("ignores late transcription after switching project and aborts its request", async () => {
  let finish!: (value: { text: string; language: "en-US" }) => void;
  vi.mocked(transcribeQuestion).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const receive = vi.fn();
  const { result, rerender } = renderHook(({ project }) => useVoiceRecorder(project, receive), { initialProps: { project: "first" } });
  await act(async () => { await result.current.start("en-US"); });
  act(() => result.current.stop());
  rerender({ project: "second" });
  await act(async () => { finish({ text: "old project question", language: "en-US" }); });
  expect(receive).not.toHaveBeenCalled();
  expect(vi.mocked(transcribeQuestion).mock.calls[0]?.[3]?.aborted).toBe(true);
});

it("releases tracks on unmount and does not upload cancelled audio", async () => {
  const { result, unmount } = renderHook(() => useVoiceRecorder("p", vi.fn()));
  await act(async () => { await result.current.start("en-US"); });
  unmount();
  expect(track.stop).toHaveBeenCalled();
  expect(transcribeQuestion).not.toHaveBeenCalled();
});

it("offers a text fallback after denied microphone permission", async () => {
  getUserMedia.mockRejectedValue(new DOMException("denied", "NotAllowedError"));
  const { result } = renderHook(() => useVoiceRecorder("p", vi.fn()));
  await act(async () => { await result.current.start("en-US"); });
  expect(result.current.error).toBe("denied");
  expect(result.current.phase).toBe("idle");
});

it("stops automatically at sixty seconds", async () => {
  vi.useFakeTimers();
  const { result } = renderHook(() => useVoiceRecorder("p", vi.fn()));
  await act(async () => { await result.current.start("es-419"); });
  await act(async () => { vi.advanceTimersByTime(60000); });
  expect(track.stop).toHaveBeenCalled();
  expect(transcribeQuestion).toHaveBeenCalledTimes(1);
});

it("keeps existing question text owned by its parent when transcription fails", async () => {
  vi.mocked(transcribeQuestion).mockRejectedValue(new Error("provider down"));
  const receive = vi.fn();
  const { result } = renderHook(() => useVoiceRecorder("p", receive));
  await act(async () => { await result.current.start("en-US"); result.current.stop(); });
  await waitFor(() => expect(result.current.error).toBe("transcription"));
  expect(receive).not.toHaveBeenCalled();
});
