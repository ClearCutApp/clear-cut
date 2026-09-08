import type { ScreenplayDocument, ScreenplayDraft } from "../../api/client";

export interface SaveState { version: number; dirty: boolean; saving: boolean; error: unknown; }
/** Serialize optimistic writes. A response updates the version, never the editor content. */
export class DraftAutosave {
  private pending: ScreenplayDocument | null = null;
  private running: Promise<void> | null = null;
  private paused = false;
  private disposed = false;
  private state: SaveState;
  constructor(version: number, private save: (version: number, document: ScreenplayDocument) => Promise<ScreenplayDraft>, private notify: (state: SaveState) => void) {
    this.state = { version, dirty: false, saving: false, error: null };
  }
  change(document: ScreenplayDocument): void {
    this.pending = document;
    this.update({ dirty: true });
  }
  private update(patch: Partial<SaveState>): void {
    this.state = { ...this.state, ...patch };
    if (!this.disposed) this.notify(this.state);
  }
  flush(): Promise<void> {
    if (this.running) return this.running;
    if (this.paused || this.disposed) return Promise.reject(this.state.error ?? new Error("Save paused"));
    this.running = this.drain().finally(() => { this.running = null; });
    return this.running;
  }
  private async drain(): Promise<void> {
    while (this.pending && !this.disposed) {
      const document = this.pending;
      this.pending = null;
      this.update({ saving: true, error: null });
      try {
        const saved = await this.save(this.state.version, document);
        this.update({ version: saved.version, dirty: this.pending !== null, saving: false });
      } catch (error) {
        this.pending ??= document;
        this.paused = true;
        this.update({ saving: false, dirty: true, error });
        throw error;
      }
    }
  }
  retry(): Promise<void> { this.paused = false; return this.flush(); }
  dispose(): void { this.disposed = true; }
  version(): number { return this.state.version; }
}
