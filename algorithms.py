from collections import deque
from itertools import product
import time

OPERATORS = ["fill_a", "fill_b", "empty_a", "empty_b", "pour_a_b", "pour_b_a"]
GOAL_MODES = ["either", "a", "b", "total"]

OP_LABEL = {
    "fill_a":   "Isi galon A sampai penuh",
    "fill_b":   "Isi galon B sampai penuh",
    "empty_a":  "Kosongkan galon A",
    "empty_b":  "Kosongkan galon B",
    "pour_a_b": "Tuang A -> B",
    "pour_b_a": "Tuang B -> A",
}

class Problem:
    def __init__(self, cap_a, cap_b, target, start=(0, 0),
                 goal_mode="either", operator_order=None,
                 use_visited=True, max_expansions=100000,
                 gt_max_length=20):
        self.cap_a = cap_a
        self.cap_b = cap_b
        self.target = target
        self.start = tuple(start)
        self.goal_mode = goal_mode
        self.operator_order = list(operator_order or OPERATORS)
        self.use_visited = use_visited
        self.max_expansions = max_expansions
        self.gt_max_length = gt_max_length

def apply_op(state, op, cap_a, cap_b):
    x, y = state
    if op == "fill_a":
        return (cap_a, y)
    if op == "fill_b":
        return (x, cap_b)
    if op == "empty_a":
        return (0, y)
    if op == "empty_b":
        return (x, 0)
    if op == "pour_a_b":
        t = min(x, cap_b - y)
        return (x - t, y + t)
    if op == "pour_b_a":
        t = min(y, cap_a - x)
        return (x + t, y - t)
    raise ValueError(f"Operator tidak dikenal: {op}")

def successors(state, problem):
    """Hasilkan (aksi, state_baru) menurut urutan operator di konfigurasi.
    Aksi yang tidak mengubah state (no-op) dilewati."""
    for op in problem.operator_order:
        new = apply_op(state, op, problem.cap_a, problem.cap_b)
        if new != state:
            yield op, new

def is_goal(state, problem):
    x, y = state
    t = problem.target
    if problem.goal_mode == "either":
        return x == t or y == t
    if problem.goal_mode == "a":
        return x == t
    if problem.goal_mode == "b":
        return y == t
    return x + y == t  # "total"

def _path(node):
    out = []
    while node is not None:
        out.append((node[2], node[0]))
        node = node[1]
    return list(reversed(out))


def _result(status, goal_node, expanded, max_frontier, elapsed):
    path = _path(goal_node) if goal_node else None
    steps = len(path) - 1 if path else None
    return {
        "status": status,          # SOLUTION | NO_SOLUTION | LIMIT_REACHED
        "path": path,              # [(aksi, state), ...] ; aksi awal = None
        "steps": steps,
        "cost": steps,             # biaya tiap aksi = 1
        "expanded": expanded,
        "max_frontier": max_frontier,
        "time": elapsed,
    }

def bfs(problem, trace=False):
    t0 = time.perf_counter()
    root = (problem.start, None, None, 0)
    frontier = deque([root])
    visited = {problem.start} if problem.use_visited else set()
    expanded, max_frontier = 0, 1

    while frontier:
        if expanded >= problem.max_expansions:
            return _result("LIMIT_REACHED", None, expanded, max_frontier,
                           time.perf_counter() - t0)
        node = frontier.popleft()
        expanded += 1
        if trace:
            print(f"  [{expanded:>4}] expand {node[0]} (kedalaman {node[3]})")
        if is_goal(node[0], problem):
            return _result("SOLUTION", node, expanded, max_frontier,
                           time.perf_counter() - t0)
        for op, new in successors(node[0], problem):
            if problem.use_visited:
                if new in visited:
                    continue
                visited.add(new)
            frontier.append((new, node, op, node[3] + 1))
        max_frontier = max(max_frontier, len(frontier))
        if trace:
            print(f"         frontier (depan -> belakang): "
                  f"{[n[0] for n in frontier]}")
    return _result("NO_SOLUTION", None, expanded, max_frontier,
                   time.perf_counter() - t0)

def dfs(problem, trace=False):
    t0 = time.perf_counter()
    root = (problem.start, None, None, 0)
    frontier = [root]
    explored = set()
    expanded, max_frontier = 0, 1

    while frontier:
        if expanded >= problem.max_expansions:
            return _result("LIMIT_REACHED", None, expanded, max_frontier,
                           time.perf_counter() - t0)
        node = frontier.pop()
        if problem.use_visited:
            if node[0] in explored:
                continue
            explored.add(node[0])
        expanded += 1
        if trace:
            print(f"  [{expanded:>4}] expand {node[0]} (kedalaman {node[3]})")
        if is_goal(node[0], problem):
            return _result("SOLUTION", node, expanded, max_frontier,
                           time.perf_counter() - t0)
        children = [(new, node, op, node[3] + 1)
                    for op, new in successors(node[0], problem)
                    if not (problem.use_visited and new in explored)]
        frontier.extend(reversed(children))
        max_frontier = max(max_frontier, len(frontier))
        if trace:
            print(f"         frontier (dasar -> puncak stack): "
                  f"{[n[0] for n in frontier]}")
    return _result("NO_SOLUTION", None, expanded, max_frontier,
                   time.perf_counter() - t0)
