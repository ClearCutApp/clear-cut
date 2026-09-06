/**
 * The questions offered as chips. One carries a legal stem ("permission",
 * "trademark") and one a blocker word: the two things the mock scenario
 * answers with a bible fact and a citation rather than a shrug, so the
 * first click on a fresh install shows a grounded answer.
 */
export const EXAMPLE_QUESTIONS: readonly string[] = [
  "Do we need permission for the trademark?",
  "What is blocked right now?",
];

/** A question worth sending: something besides whitespace. */
export function isAskable(question: string): boolean {
  return question.trim().length > 0;
}
