#!/usr/bin/env bash
#
# init.sh — bootstrap and verify the ClearCut agent loop.
#
#   ./.claude/init.sh            bootstrap, then verify
#   ./.claude/init.sh verify     static checks on the loop configuration
#   ./.claude/init.sh check      run the project quality gates (ruff, mypy, pytest,
#                                web lint:css, typecheck, vitest)
#   ./.claude/init.sh live       run the tests that reach real services
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="$ROOT/.claude"
AGENTS="$CFG/agents"
ROLES=(leader implementer reviewer)
STATUSES=(TODO IN_PROGRESS IN_REVIEW DONE BLOCKED SUPERSEDED)

pass=0; fail=0
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
no()   { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }
note() { printf '  \033[33m•\033[0m %s\n' "$1"; }
sec()  { printf '\n\033[1m%s\033[0m\n' "$1"; }

# frontmatter of a .md file: the lines between the first two --- markers
frontmatter() { awk 'NR==1&&/^---$/{f=1;next} f&&/^---$/{exit} f' "$1"; }
field()       { frontmatter "$1" | sed -n "s/^$2:[[:space:]]*//p" | head -1; }

# ---------------------------------------------------------------- verify ----
verify() {
  sec "Files"
  for f in AGENT.md WRITING.md CHECKPOINTS.md settings.json settings.local.json init.sh; do
    [ -f "$CFG/$f" ] && ok ".claude/$f" || no ".claude/$f is missing"
  done
  for r in "${ROLES[@]}"; do
    [ -f "$AGENTS/$r.md" ] && ok ".claude/agents/$r.md" || no ".claude/agents/$r.md is missing"
  done
  [ -x "$CFG/init.sh" ] && ok "init.sh is executable" || no "init.sh is not executable"

  sec "Agent frontmatter"
  for r in "${ROLES[@]}"; do
    f="$AGENTS/$r.md"; [ -f "$f" ] || continue
    [ "$(field "$f" name)" = "$r" ] && ok "$r: name matches filename" \
      || no "$r: frontmatter name '$(field "$f" name)' != '$r'"
    [ -n "$(field "$f" description)" ] && ok "$r: has a description" \
      || no "$r: description is empty (agent cannot be selected)"
    [ -n "$(field "$f" tools)" ] && ok "$r: declares tools" \
      || no "$r: no tools declared (would inherit everything)"
  done

  sec "Tool boundaries (separation of concerns)"
  rt="$(field "$AGENTS/reviewer.md" tools)"
  case "$rt" in
    *Write*) no "reviewer may Write — it must report, not fix" ;;
    *)       ok "reviewer cannot Write source files" ;;
  esac
  case "$rt" in
    *Edit*) ok "reviewer can Edit (CHECKPOINTS.md status)" ;;
    *)      no "reviewer cannot Edit — it could not record a verdict" ;;
  esac
  it="$(field "$AGENTS/implementer.md" tools)"
  for t in Write Edit Bash; do
    case "$it" in *"$t"*) ok "implementer can $t" ;; *) no "implementer cannot $t" ;; esac
  done
  grep -q 'only file you may write' "$AGENTS/leader.md" \
    && ok "leader is restricted to CHECKPOINTS.md in prose" \
    || no "leader has no write restriction stated"
  grep -q 'only file you may edit' "$AGENTS/reviewer.md" \
    && ok "reviewer is restricted to CHECKPOINTS.md in prose" \
    || no "reviewer has no edit restriction stated"

  sec "Memory grants (Engram)"
  mem_read="mem_search"; mem_write="mem_save"
  for r in "${ROLES[@]}"; do
    t="$(field "$AGENTS/$r.md" tools)"
    case "$t" in
      *"$mem_read"*) ok "$r can read memory" ;;
      *)             no "$r cannot read memory — no mem_search grant" ;;
    esac
  done
  lt="$(field "$AGENTS/leader.md" tools)"
  case "$lt" in
    *"$mem_write"*) ok "leader can write memory" ;;
    *)              no "leader cannot write memory — nobody can record decisions" ;;
  esac
  for r in implementer reviewer; do
    t="$(field "$AGENTS/$r.md" tools)"
    case "$t" in
      *"$mem_write"*) no "$r may write memory — unreviewed state" ;;
      *)              ok "$r cannot write memory" ;;
    esac
  done

  sec "Contract references"
  for r in "${ROLES[@]}"; do
    f="$AGENTS/$r.md"; [ -f "$f" ] || continue
    grep -q 'AGENT.md' "$f"       && ok "$r reads AGENT.md"       || no "$r never reads AGENT.md"
    grep -q 'CHECKPOINTS.md' "$f" && ok "$r reads CHECKPOINTS.md" || no "$r never reads CHECKPOINTS.md"
  done

  sec "Handoff wiring"
  for r in "${ROLES[@]}"; do
    f="$AGENTS/$r.md"; [ -f "$f" ] || continue
    grep -q "^ROLE: $r$" "$f" && ok "$r emits its handoff block" || no "$r has no 'ROLE: $r' block"
  done
  grep -q '^NEXT: implementer' "$AGENTS/leader.md"    && ok "leader      -> implementer" || no "leader does not hand off to implementer"
  grep -q '^NEXT: reviewer'    "$AGENTS/implementer.md" && ok "implementer -> reviewer"   || no "implementer does not hand off to reviewer"
  grep -q '^NEXT: implementer' "$AGENTS/reviewer.md"  && ok "reviewer    -> implementer (rework)" || no "reviewer cannot send work back"
  grep -q 'leader CP'          "$AGENTS/reviewer.md"  && ok "reviewer    -> leader (escalate)"    || no "reviewer cannot escalate"
  grep -q 'done$'              "$AGENTS/reviewer.md"  && ok "reviewer    -> done (exit)"          || no "reviewer has no exit path"

  sec "Termination guarantees"
  grep -q '3/3' "$AGENTS/reviewer.md" && ok "attempt cap enforced by reviewer" || no "reviewer never enforces the attempt cap"
  grep -q '3/3' "$CFG/CHECKPOINTS.md" && ok "attempt cap documented in state"  || no "CHECKPOINTS.md omits the attempt cap"
  grep -q 'never send work back' "$AGENTS/reviewer.md" \
    && ok "non-blocking findings cannot re-open a checkpoint" \
    || no "non-blocking findings could loop forever"
  grep -q 'BLOCKED' "$AGENTS/leader.md" && ok "leader absorbs BLOCKED checkpoints" || no "BLOCKED has no consumer — the loop can deadlock"
  grep -q 'never move a checkpoint from' "$AGENTS/leader.md" \
    && ok "leader cannot reset BLOCKED back to TODO" \
    || no "leader may reset BLOCKED — unbounded rework"
  grep -q 'never supersede a `Depth: 1`' "$AGENTS/leader.md" \
    && ok "leader is bound to one generation of splits" \
    || no "leader may split without bound"
  grep -q 'Depth: 0' "$CFG/CHECKPOINTS.md" \
    && ok "checkpoint template carries Depth" \
    || no "CHECKPOINTS.md template has no Depth field"

  sec "Prose contract (WRITING.md)"
  grep -q 'WRITING.md' "$CFG/AGENT.md" \
    && ok "AGENT.md points at the prose contract" \
    || no "AGENT.md never references WRITING.md"
  grep -q 'WRITING.md' "$AGENTS/reviewer.md" \
    && ok "reviewer checks prose against WRITING.md" \
    || no "reviewer never applies the prose contract"
  grep -q 'WRITING.md' "$AGENTS/implementer.md" \
    && ok "implementer writes to the prose contract" \
    || no "implementer never reads the prose contract"
  grep -q '^## 0\. Scope' "$CFG/WRITING.md" \
    && ok "WRITING.md declares its scope" \
    || no "WRITING.md has no scope — would apply to specs too"
  grep -q '\*\*Non-blocking\*\*' "$CFG/WRITING.md" \
    && ok "prose findings can be non-blocking" \
    || no "all prose findings block — style can spin the loop past 3 attempts"
  grep -q 'new and changed lines only' "$AGENTS/reviewer.md" \
    && ok "prose review is scoped to the diff" \
    || no "reviewer could raise findings on untouched prose"

  sec "Boundary with gentle-ai"
  grep -q '^## 11\. Relationship to gentle-ai' "$CFG/AGENT.md" \
    && ok "AGENT.md declares the gentle-ai boundary" \
    || no "no gentle-ai boundary section — two processes could coexist silently"
  grep -q 'Do not use the SDD pipeline in this repo' "$CFG/AGENT.md" \
    && ok "SDD pipeline is excluded from this repo" \
    || no "SDD pipeline is not excluded — competing loop"
  grep -q '\*\*AGENT.md wins\*\*' "$CFG/AGENT.md" \
    && ok "AGENT.md wins over skills on conflict" \
    || no "no conflict rule between skills and AGENT.md"
  grep -q 'Never run both' "$CFG/AGENT.md" \
    && ok "switching to SDD is a migration, not a drift" \
    || no "nothing forbids running both loops"
  if grep -lE '/sdd-(init|new|apply|verify|tasks|spec|design)' "$AGENTS"/*.md >/dev/null 2>&1; then
    no "an agent invokes an SDD command: $(grep -lE '/sdd-' "$AGENTS"/*.md | xargs -n1 basename | tr '\n' ' ')"
  else
    ok "no agent invokes the SDD pipeline"
  fi
  if command -v gentle-ai >/dev/null 2>&1; then
    ok "gentle-ai present ($(gentle-ai --version 2>/dev/null | head -1))"
  else
    note "gentle-ai not on PATH — optional; add \$HOME/go/bin to PATH"
  fi

  sec "Status machine"
  for s in "${STATUSES[@]}"; do
    grep -q "\`$s\`" "$CFG/AGENT.md" && ok "$s is defined in AGENT.md" || no "$s is not in the AGENT.md status table"
  done
  used="$(grep -ohE '\bStatus: [A-Z_]+' "$AGENTS"/*.md | sed 's/Status: //' | sort -u || true)"
  for s in $used; do
    printf '%s\n' "${STATUSES[@]}" | grep -qx "$s" \
      && ok "agents use a known status: $s" \
      || no "agents use an undefined status: $s"
  done

  sec "Loop termination (proved from the AGENT.md status table)"
  out="$(python3 "$CFG/lib/termination.py" "$CFG/AGENT.md" || true)"
  while IFS= read -r line; do
    case "$line" in
      OK\ *)      ok "${line#OK }" ;;
      PROBLEM\ *) no "${line#PROBLEM }" ;;
      "")         ;;
      *)          note "$line" ;;
    esac
  done <<< "$out"

  sec "Settings"
  for f in settings.json settings.local.json; do
    python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$CFG/$f" 2>/dev/null \
      && ok "$f is valid JSON" || no "$f is not valid JSON"
  done
  grep -q '\.claude/settings\.local\.json' "$ROOT/.gitignore" 2>/dev/null \
    && ok "settings.local.json is gitignored" || no "settings.local.json would be committed"
  grep -q '^\.env$' "$ROOT/.gitignore" 2>/dev/null \
    && ok ".env is gitignored" || no ".env would be committed"

  sec "Result"
  printf '  %d passed, %d failed\n\n' "$pass" "$fail"
  [ "$fail" -eq 0 ]
}

# ------------------------------------------------------------- bootstrap ----
bootstrap() {
  sec "Bootstrap"
  chmod +x "$CFG/init.sh"; ok "init.sh executable"

  if [ -f "$ROOT/pyproject.toml" ] || [ -f "$ROOT/requirements.txt" ]; then
    if [ ! -d "$ROOT/.venv" ]; then
      python3 -m venv "$ROOT/.venv" && ok "created .venv"
    else
      ok ".venv present"
    fi
    # shellcheck disable=SC1091
    . "$ROOT/.venv/bin/activate"
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -e "${ROOT}[dev]" && ok "clearcut + dev tools installed"
    note "activate with: source .venv/bin/activate"
  else
    note "no pyproject.toml / requirements.txt yet — nothing to install"
    note "the first checkpoint should create the project skeleton (AGENT.md §2)"
  fi
}

# ----------------------------------------------------------------- check ----
# `cmd && ok "x"` alone never fails this function under `set -e`: a failing
# command that is not the last one in an AND-OR list does not trigger `-e`
# (POSIX), so a bare `&&` here would let a broken gate report success. Each
# step instead follows `verify()`'s own `ok`/`no` bookkeeping, and the
# function returns non-zero exactly when `no` fired.
#
# A gate that cannot run is a failure, not a silence. `note` increments neither
# counter, so using it here let a machine with no ruff, no mypy, no pytest and
# no web/node_modules print "0 passed, 0 failed" and exit success — absence
# reading as success, the same defect the live tier exists to close. Every
# unrunnable gate below calls `no`.
check() {
  sec "Quality gates"
  [ -d "$ROOT/.venv" ] && . "$ROOT/.venv/bin/activate"
  if command -v ruff >/dev/null 2>&1; then
    ruff check "$ROOT" && ok "ruff check" || no "ruff check"
    ruff format --check "$ROOT" && ok "ruff format" || no "ruff format"
  else
    no "ruff not installed — run ./.claude/init.sh first"
  fi
  if command -v mypy >/dev/null 2>&1 && [ -d "$ROOT/src" ]; then
    (cd "$ROOT" && mypy src tests infra main.py) && ok "mypy" || no "mypy"
  else
    no "mypy not installed — run ./.claude/init.sh first"
  fi
  if command -v pytest >/dev/null 2>&1 && [ -d "$ROOT/tests" ]; then
    (cd "$ROOT" && pytest -q) && ok "pytest" || no "pytest"
  else
    no "pytest not installed or no tests/ — run ./.claude/init.sh first"
  fi
  if [ -d "$ROOT/web/node_modules" ]; then
    (cd "$ROOT/web" && npm run lint:css) && ok "web lint:css" || no "web lint:css"
    (cd "$ROOT/web" && npm run typecheck) && ok "web typecheck" || no "web typecheck"
    (cd "$ROOT/web" && npm test) && ok "web test" || no "web test"
  else
    no "web/node_modules missing — run npm install in web/ first"
  fi
  sec "Result"
  printf '  %d passed, %d failed\n\n' "$pass" "$fail"
  [ "$fail" -eq 0 ]
}

# ------------------------------------------------------------------ live ----
# The gate `check` cannot be: tests that reach a real external service. Each one
# skips itself when its own credentials are absent, so an all-skipped run is the
# honest answer on an unconfigured machine — and is reported as such rather than
# counted as proof. Deselected from `check` by the `-m "not live"` default in
# pyproject.toml, so this is the only way to run them.
live() {
  sec "Live service gates"
  [ -d "$ROOT/.venv" ] && . "$ROOT/.venv/bin/activate"
  if command -v pytest >/dev/null 2>&1 && [ -d "$ROOT/tests/live" ]; then
    # `pytest` exits 0 when every test skips, so the exit code alone cannot
    # tell "ten services answered" from "nothing was contacted". Both were
    # reported as a pass until 2026-09-05, which is how a reconciliation came
    # to cite ten live passes that had never run. Read the summary too.
    live_status=0
    live_out="$(cd "$ROOT" && pytest -m live -q -rs 2>&1)" || live_status=$?
    printf '%s\n' "$live_out"
    if [ "$live_status" -ne 0 ]; then
      no "pytest -m live"
    elif printf '%s' "$live_out" | grep -Eq '[0-9]+ passed'; then
      ok "pytest -m live"
    else
      no "pytest -m live contacted nothing — every live test skipped, so this run is a configuration gap, not proof. The reasons above name the variables each test wanted."
    fi
  else
    no "pytest not installed or tests/live/ missing — run ./.claude/init.sh first"
  fi
  sec "Result"
  printf '  %d passed, %d failed\n\n' "$pass" "$fail"
  [ "$fail" -eq 0 ]
}

case "${1:-bootstrap}" in
  verify)    verify ;;
  check)     check ;;
  live)      live ;;
  bootstrap) bootstrap; verify ;;
  *) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
