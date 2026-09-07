import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { QuestionForm } from "./QuestionForm";
vi.mock("../voice/VoiceQuestion", () => ({ VoiceQuestion: ({ onTranscript }: { onTranscript: (text: string) => void }) => <button type="button" onClick={() => onTranscript("Can we use this mural?")}>Finish transcription</button> }));
it("preserves typed text and requires explicit submission after editable transcription", () => {
  const ask = vi.fn();
  render(<QuestionForm projectId="p" examples={[]} submitting={false} error={null} onAsk={ask} />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Scene two." } });
  fireEvent.click(screen.getByRole("button", { name: "Finish transcription" }));
  expect(ask).not.toHaveBeenCalled();
  expect(screen.getByRole("textbox")).toHaveValue("Scene two.\nCan we use this mural?");
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Can we use the exterior mural?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(ask).toHaveBeenCalledWith("Can we use the exterior mural?");
});
