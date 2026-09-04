import { ApiError } from "../api/client";

/**
 * The result of a data-layer action, for callers that render outcomes
 * rather than catch exceptions: a view shows `message` in an `ErrorNotice`
 * and never sees a thrown error.
 */
export type Outcome<T> =
  | { ok: true; value: T }
  | { ok: false; message: string };

export function succeed<T>(value: T): Outcome<T> {
  return { ok: true, value };
}

export function fail<T>(message: string): Outcome<T> {
  return { ok: false, message };
}

/**
 * `ApiError.message` is the server's own sentence (a 400 body such as
 * "gcs_uri is required"), worth showing verbatim. Anything else is not
 * evidence about the request, so it becomes the caller's `fallback`.
 */
export function failureMessage(thrown: unknown, fallback: string): string {
  return thrown instanceof ApiError ? thrown.message : fallback;
}

/** Runs `request` and folds its promise into an `Outcome`. */
export async function attempt<T>(
  request: () => Promise<T>,
  fallback: string,
): Promise<Outcome<T>> {
  try {
    return succeed(await request());
  } catch (thrown) {
    return fail(failureMessage(thrown, fallback));
  }
}
