import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

from algorithms import (ALGORITHMS, GOAL_MODES, OP_LABEL, OPERATORS, Problem)

DEFAULTS = {
    "start": [0, 0],
    "goal_mode": "either",            # either | a | b | total
    "operator_order": OPERATORS,      # urutan operator = urutan tetangga
    "use_visited": True,              # False -> uji tanpa visited set
    "max_expansions": 100000,         # pengaman agar tidak berputar selamanya
    "gt_max_length": 20,              # panjang maks kandidat Generate and Test
}
DEFAULT_REPEAT = 5
LOG_FILE = os.path.join("results", "log.csv")


class InputError(Exception):
    pass


def load_problem(path):
    """Baca & validasi file input JSON. Lempar InputError dengan pesan jelas."""
    if not os.path.isfile(path):
        raise InputError(f"File input tidak ditemukan: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise InputError(f"Format JSON salah di {path}: {e}")
    if not isinstance(data, dict):
        raise InputError("Isi file input harus berupa objek JSON { ... }.")

    for key in ("capacity_a", "capacity_b", "target"):
        if key not in data:
            raise InputError(f"Field wajib '{key}' tidak ada di {path}.")
    cfg = {**DEFAULTS, **data}

    def is_int(v):
        return isinstance(v, int) and not isinstance(v, bool)

    if not (is_int(cfg["capacity_a"]) and cfg["capacity_a"] > 0):
        raise InputError("capacity_a harus bilangan bulat > 0.")
    if not (is_int(cfg["capacity_b"]) and cfg["capacity_b"] > 0):
        raise InputError("capacity_b harus bilangan bulat > 0.")
    if not (is_int(cfg["target"]) and cfg["target"] >= 0):
        raise InputError("target harus bilangan bulat >= 0.")
    st = cfg["start"]
    if not (isinstance(st, list) and len(st) == 2 and all(is_int(v) for v in st)):
        raise InputError("start harus berupa list dua bilangan bulat, mis. [0, 0].")
    if not (0 <= st[0] <= cfg["capacity_a"] and 0 <= st[1] <= cfg["capacity_b"]):
        raise InputError("start melebihi kapasitas galon.")
    if cfg["goal_mode"] not in GOAL_MODES:
        raise InputError(f"goal_mode harus salah satu dari {GOAL_MODES}.")
    order = cfg["operator_order"]
    if (not isinstance(order, list) or not order
            or any(o not in OPERATORS for o in order)):
        raise InputError(f"operator_order harus list tidak kosong berisi {OPERATORS}.")
    if not (is_int(cfg["max_expansions"]) and cfg["max_expansions"] > 0):
        raise InputError("max_expansions harus bilangan bulat > 0.")

    if not (is_int(cfg["gt_max_length"]) and cfg["gt_max_length"] > 0):
        raise InputError("gt_max_length harus bilangan bulat > 0.")

    return Problem(cfg["capacity_a"], cfg["capacity_b"], cfg["target"],
                   start=st, goal_mode=cfg["goal_mode"],
                   operator_order=order, use_visited=bool(cfg["use_visited"]),
                   max_expansions=cfg["max_expansions"],
                   gt_max_length=cfg["gt_max_length"])


def print_problem(p, path):
    print("=" * 64)
    print(f"Input          : {path}")
    print(f"Galon A / B    : {p.cap_a} L / {p.cap_b} L")
    print(f"Start          : {p.start}")
    print(f"Target         : {p.target} L (mode: {p.goal_mode})")
    print(f"Urutan operator: {', '.join(p.operator_order)}")
    print(f"Visited set    : {'aktif' if p.use_visited else 'NONAKTIF'}")
    print("=" * 64)


def print_summary(name, r, repeat, avg_time):
    print(f"\n--- {name.upper()} ---")
    if r["status"] == "SOLUTION":
        print("Status             : solusi ditemukan")
        print(f"Jumlah langkah     : {r['steps']}")
        print(f"Biaya total        : {r['cost']}")
        print("Jalur solusi       :")
        for i, (op, st) in enumerate(r["path"]):
            label = "Keadaan awal" if op is None else OP_LABEL[op]
            print(f"  {i:>3}. {st}  <- {label}")
    elif r["status"] == "NO_SOLUTION":
        print("Status             : TIDAK ADA SOLUSI "
              "(seluruh ruang keadaan sudah dijelajahi)")
    else:
        print("Status             : DIHENTIKAN - batas max_expansions / "
              "gt_max_length tercapai (belum tentu tidak ada solusi)")
    print(f"Node expanded      : {r['expanded']}"
          + (" (kandidat diuji)" if name == "gt" else ""))
    if name == "gt":
        print("Ukuran frontier max: - (Generate and Test tidak punya frontier)")
    else:
        print(f"Ukuran frontier max: {r['max_frontier']}")
    print(f"Waktu eksekusi     : {avg_time * 1000:.4f} ms "
          f"(rata-rata {repeat}x)")


def append_log(path_in, algo, r, repeat, avg_time):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    new = not os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "input", "algo", "status", "steps", "cost",
                        "expanded", "max_frontier", "avg_time_ms", "repeat"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), path_in, algo,
                    r["status"], r["steps"], r["cost"], r["expanded"],
                    r["max_frontier"], f"{avg_time * 1000:.4f}", repeat])


def main():
    ap = argparse.ArgumentParser(description="Water Jug: BFS, DFS, Generate and Test")
    ap.add_argument("--input", required=True, help="file input JSON")
    ap.add_argument("--algo", choices=["bfs", "dfs", "gt", "both", "all"], default="all",
                    help="gt = Generate and Test; both = bfs+dfs; all = ketiganya")
    ap.add_argument("--trace", action="store_true",
                    help="cetak node yang di-expand dan isi frontier")
    ap.add_argument("--repeat", type=int, default=DEFAULT_REPEAT,
                    help="ulang pengukuran waktu (default 5)")
    ap.add_argument("--log", action="store_true",
                    help=f"tambahkan hasil ke {LOG_FILE}")
    args = ap.parse_args()

    try:
        problem = load_problem(args.input)
    except InputError as e:
        print(f"[ERROR INPUT] {e}", file=sys.stderr)
        return 1
    if args.repeat < 1:
        print("[ERROR] --repeat harus >= 1", file=sys.stderr)
        return 1

    print_problem(problem, args.input)
    names = {"all": ["bfs", "dfs", "gt"], "both": ["bfs", "dfs"]}.get(args.algo, [args.algo])

    for name in names:
        fn = ALGORITHMS[name]
        if args.trace:
            print(f"\n[TRACE {name.upper()}]")
        r = fn(problem, trace=args.trace)      # run pertama (boleh dengan trace)
        times = [r["time"]]
        for _ in range(args.repeat - 1):       # sisanya hanya untuk waktu
            times.append(fn(problem)["time"])
        avg = sum(times) / len(times)
        print_summary(name, r, args.repeat, avg)
        if args.log:
            append_log(args.input, name, r, args.repeat, avg)

    return 0


if __name__ == "__main__":
    sys.exit(main())
