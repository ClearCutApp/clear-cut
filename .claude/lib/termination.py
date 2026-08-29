"""Prove the ClearCut agent loop terminates.

Reads the status-machine table in AGENT.md (§7) and checks four properties:
every status is reachable, no status is a trap, every cycle is guarded by the
attempt counter, and every transition has exactly one owning role.

Called by `./.claude/init.sh verify`. Prints OK/PROBLEM lines; exits non-zero
if any property fails.
"""

import re
import sys

ROLES = {"leader", "implementer", "reviewer"}
START = "TODO"
ROW = re.compile(r"^\|\s*`(\w+)`\s*\|\s*`(\w+)`([^|]*)\|\s*(\w+)\s*\|")
TERMINAL_DECL = re.compile(r"^Terminal statuses:\s*(.+)$")


def parse(path):
    """-> ([(from, to, guarded_by_attempt_counter, owning_role)], declared_terminals)

    Terminals are read from the explicit `Terminal statuses:` declaration, never
    inferred from dead ends — a dead end that nobody declared terminal is a bug,
    and inferring would hide exactly that bug.
    """
    edges, terminals = [], set()
    for line in open(path, encoding="utf-8"):
        m = ROW.match(line)
        if m:
            edges.append((m[1], m[2], "attempt" in m[3].lower(), m[4]))
        d = TERMINAL_DECL.match(line)
        if d:
            terminals |= set(re.findall(r"`(\w+)`", d[1]))
    return edges, terminals


def reachable_from(adj, start):
    seen, stack = set(), [start]
    while stack:
        for nxt in adj.get(stack.pop(), []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def cycles_from(adj, start):
    found, path = [], []

    def walk(node, on_path):
        path.append(node)
        for nxt in adj.get(node, []):
            if nxt in on_path:
                found.append(path[path.index(nxt):] + [nxt])
            else:
                walk(nxt, on_path | {nxt})
        path.pop()

    walk(start, {start})
    return found


def check(edges, terminals):
    """-> list of report lines, each prefixed OK or PROBLEM."""
    nodes = {e[0] for e in edges} | {e[1] for e in edges}
    adj = {n: [e[1] for e in edges if e[0] == n] for n in nodes}
    out = []

    if not terminals:
        out.append("PROBLEM AGENT.md declares no `Terminal statuses:` line")
        return out
    undeclared = sorted(n for n in nodes - terminals if not adj[n])
    out.append(
        f"PROBLEM dead ends that are not declared terminal: {undeclared}"
        if undeclared
        else f"OK every dead end is a declared terminal ({', '.join(sorted(terminals))})"
    )
    leaky = sorted(n for n in terminals & nodes if adj[n])
    out.append(
        f"PROBLEM declared terminal with outgoing transitions: {leaky}"
        if leaky
        else f"OK declared terminals have no way out ({len(terminals)})"
    )

    unreachable = nodes - reachable_from(adj, START) - {START}
    out.append(
        f"PROBLEM unreachable from {START}: {sorted(unreachable)}"
        if unreachable
        else f"OK all {len(nodes)} statuses reachable from {START}"
    )

    traps = sorted(n for n in nodes - terminals if not reachable_from(adj, n) & terminals)
    out.append(
        f"PROBLEM trap states, cannot terminate: {traps}"
        if traps
        else "OK every non-terminal status reaches a declared terminal"
    )

    cycles = cycles_from(adj, START)
    for cyc in cycles:
        pairs = set(zip(cyc, cyc[1:]))
        guards = [e for e in edges if e[2] and (e[0], e[1]) in pairs]
        out.append(
            f"OK cycle guarded by {guards[0][0]}->{guards[0][1]} (+1 attempt): {' -> '.join(cyc)}"
            if guards
            else f"PROBLEM unbounded cycle, no attempt counter: {' -> '.join(cyc)}"
        )
    out.append(f"OK exactly {len(cycles)} cycle(s) in the machine")

    unowned = [(a, b, who) for a, b, _, who in edges if who not in ROLES]
    out.append(
        f"PROBLEM transitions with an unknown owner: {unowned}"
        if unowned
        else f"OK all {len(edges)} transitions owned by a defined role"
    )
    return out


def main(path):
    edges, terminals = parse(path)
    if not edges:
        print("PROBLEM no status table found in AGENT.md")
        return 1
    lines = check(edges, terminals)
    print("\n".join(lines))
    return 1 if any(line.startswith("PROBLEM") for line in lines) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ".claude/AGENT.md"))
