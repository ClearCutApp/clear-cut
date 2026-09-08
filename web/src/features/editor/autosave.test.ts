import { describe, expect, it, vi } from "vitest";
import { DraftAutosave, type SaveState } from "./autosave";
import { emptyScreenplay } from "./schema";
import type { ScreenplayDraft } from "../../api/client";

function saved(version: number): ScreenplayDraft { return { project_id: "p", version, document: null, updated_at: "", updated_by: "" }; }
describe("draft save queue", () => {
  it("serializes newer typing after the pending write without overwriting text", async () => {
    let finish!: (draft: ScreenplayDraft) => void;
    const first = emptyScreenplay(), second = emptyScreenplay();
    const save = vi.fn().mockImplementationOnce(() => new Promise<ScreenplayDraft>(resolve => { finish = resolve; })).mockResolvedValueOnce(saved(2));
    const notify = vi.fn();
    const queue = new DraftAutosave(0, save, notify);
    queue.change(first); const flushed = queue.flush(); queue.change(second);
    expect(save).toHaveBeenCalledTimes(1);
    finish(saved(1)); await flushed;
    expect(save.mock.calls).toEqual([[0, first], [1, second]]);
    expect(notify).toHaveBeenLastCalledWith({ version: 2, dirty: false, saving: false, error: null });
  });
  it("retains newer local changes and pauses after a conflict", async () => {
    let fail!: (error: Error) => void;
    const save = vi.fn().mockImplementationOnce(() => new Promise<ScreenplayDraft>((_resolve, reject) => { fail = reject; })).mockResolvedValueOnce(saved(1));
    const states: SaveState[] = [];
    const queue = new DraftAutosave(0, save, state => states.push(state));
    queue.change(emptyScreenplay()); const flushed = queue.flush();
    const latest = emptyScreenplay(); queue.change(latest); fail(new Error("conflict"));
    await expect(flushed).rejects.toThrow("conflict");
    await expect(queue.flush()).rejects.toThrow("conflict");
    expect(save).toHaveBeenCalledTimes(1);
    expect(states.at(-1)?.dirty).toBe(true);
    await queue.retry(); expect(save).toHaveBeenLastCalledWith(0, latest);
  });
  it("ignores a late response after leaving the project", async () => {
    let finish!: (draft: ScreenplayDraft) => void;
    const notify = vi.fn();
    const queue = new DraftAutosave(0, () => new Promise(resolve => { finish = resolve; }), notify);
    queue.change(emptyScreenplay()); const flushed = queue.flush(); queue.dispose(); notify.mockClear();
    finish(saved(1)); await flushed;
    expect(notify).not.toHaveBeenCalled();
  });
});
