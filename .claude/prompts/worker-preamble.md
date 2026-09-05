# Worker preamble

Every implementation worker on ClearCut reads this first. Your own brief names
only what differs from it.

This file exists because four workers on 2026-09-05 were each told the same
rules, and each paid to read them (`AGENT.md` section 13).

---

## Read before writing

- `.claude/AGENT.md` — the engineering contract. Section 2 layers, section 4
  design and anti-over-engineering rules, section 5 testing.
- `.claude/WRITING.md` — the prose contract. Governs docstrings, comments and
  commit messages, not only documents.
- `docs/api/openapi.yaml` — the frozen wire contract. If you serve or call an
  endpoint, this file is its specification, not a suggestion.
- `docs/plan/adr/README.md` — the index. Read the records your brief names.

Read the last ten commit messages (`git log -10`) before writing your first one.
They explain why, not what, and your messages must match that voice.

---

## The layer rule

```
adapters  ->  application  ->  domain
(I/O)         (use cases)      (rules)
```

- `domain/` imports stdlib only. If it needs the time or a random number, it
  takes it as an argument.
- `application/` defines the ports it needs as `Protocol`, and never imports
  `flask`, `google`, `clickhouse_connect`, `requests`, `httpx` or
  `opentelemetry`.
- `adapters/` translates: external shapes and errors in, domain types and domain
  errors out. Adapters hold no business rules.
- Wiring happens only in `composition.py`. Plain constructor injection, no
  container, no service locator, no globals.
- A use case is one behaviour with one public `execute`.

`tests/unit/test_layer_boundaries.py` walks every file's AST and enforces this.
It is not advisory.

---

## Testing

- **TDD.** Write the test, watch it fail for the right reason, then implement.
- **`unittest.mock` is banned** (AGENT.md section 5). Patching is a coupling
  smell. Every seam is a constructor argument and every double is hand-written
  in `tests/unit/fakes.py`, bound to its protocol by annotated assignment so
  mypy checks the shape structurally.
- No production code ships without a test that would fail without it.
- A checkpoint that introduces or changes an adapter is not done without a
  `tests/live/` test that reaches the real service, and a live test asserts on a
  value only a real response carries (D66).
- A live test has two honest outcomes: it passes with credentials, or it skips
  without them. It must never pass without them.

---

## The traps that have actually cost time

Each of these has bitten someone on this repo. They are cheap to avoid and
expensive to discover.

**Backend**

- `tests/unit/test_composition.py::test_no_adapter_module_reads_the_environment_directly`
  greps adapter files for the literal string `os.environ`. **A docstring merely
  mentioning it fails the test.**
- `tests/unit/test_environment_contract.py` asserts bidirectional equality
  between `composition.py`'s `_required_env` call sites, `.env.example` and
  `docs/plan/infrastructure.md` section 8. A new required variable lands in
  **all three in one commit**, or that gate goes red.
- A second guard reads every `requires()` name out of `tests/live/` and asserts
  each is documented in the same two files.
- `tests/unit/test_error_boundaries.py` contract-walks every adapter exception
  to exactly one of the four domain error types in `domain/errors.py`.
- `tests/unit/test_layer_boundaries.py` permits an adapter to import only its
  own package.
- The root span is opened in the route, not the use case — that is why the five
  stage spans share one trace id. The application layer cannot import
  opentelemetry.

**Frontend**

- `web/src/architecture.test.ts` fails the build on **dead CSS**: a class defined
  in a partial whose block is already in use, but rendered by no non-test
  component. **Write the component before its stylesheet.**
- `.stylelintrc.json` **bans `100vh`, `100dvh`, `100svh` and `100lvh`** on
  `height` and `min-height`. The design mockup locks the body to the viewport
  with an inner-scrolling pane; that cannot be ported. The page scrolls.
- Only `web/src/api/client.ts` may contain a quoted `/api/` path literal.
- No file under `components/atoms/` may import from `src/api/`.
- Only `web/src/app/demo.ts` may spell `demo-project`, the demo gcs uri, or
  `"AR"`.
- stylelint enforces strict BEM `block__element--modifier`, forbids ids, and
  forbids styling `[data-testid]`.
- Components carry a token or a class modifier, never a hex value.
- `web/src/testing/fetchStub.ts` classifies by method plus body, never by path,
  so a new `GET` endpoint collides with an existing kind unless you add a
  `RouteKind`.

---

## Honesty about data

This product refuses to draw what it does not have, and that discipline is a
feature rather than an obstacle.

- A control with no endpoint behind it renders **visibly disabled with a stated
  reason**, in the spirit of `ModeBanner` and the sidebar's unavailable entries.
  It is never wired to something that silently does nothing, and never given
  invented data.
- `web/src/fixtures/` is imported by tests only, never by a component.
- If your brief asks for a screen the API cannot fill, build the honest version
  and say so in your report. Do not invent a field.

---

## Gates

```bash
./.claude/init.sh check     # the seven gates
```

**7 passed, 0 failed before you finish.** Run it more than once as you go, not
once at the end. It is one Bash call: never delegate it to a subagent.

`./.claude/init.sh live` needs `.env` and reaches real services. It reports how
many tests actually ran; an all-skipped run is named as a configuration gap, not
reported as a pass.

---

## Git

- Conventional commits. Imperative mood, lowercase after the type.
- **Never `Co-Authored-By`, never any AI attribution.** This is absolute.
- Stage by explicit path. **Never `git add -A`.**
- Commit in coherent slices, not one giant commit at the end.
- Commit messages explain why. The what is in the diff.

---

## Reporting back

State plainly:

- the branch, every commit hash and subject
- the gate result, as the numbers it printed
- anything you had to leave broken because it was outside your file list
- anything that contradicted your brief

If a gate fails, say so with the output. Do not report work as finished that is
not finished. This repository has three recorded cases of a status that was
never earned, and every one of them cost more to unpick than it would have cost
to admit.
