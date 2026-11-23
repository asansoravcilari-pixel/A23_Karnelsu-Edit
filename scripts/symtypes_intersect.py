#!/usr/bin/env python3
"""Name the kernel type(s) that make OEM export CRCs differ.

Inputs
  --symtypes DIR   directory tree of genksyms ``*.symtypes`` files (KBUILD_SYMTYPES=1)
  --reference TSV  OEM module CRC reference (columns: module, symbol, stock_crc)
  --report TXT     verifier report listing ``MISMATCH <symbol>:`` lines

Method: build the type-reference graph from the .symtypes files, compute for every
reference symbol the set of types it transitively reaches, then look for types that
are reached by mismatching symbols and by NO matching symbol.  The deepest such
types (whose closure contains no other candidate) are the prime suspects.

This is diagnostic evidence only.  It never approves flashing and never changes CRCs.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

TYPE_REF = re.compile(r"^[sute]#[A-Za-z0-9_.$]+$")
MISMATCH_RE = re.compile(r"MISMATCH\s+(\S+?):")


def load_symtypes(root: Path) -> dict[str, list[str]]:
    """Merge all ``*.symtypes`` under *root*; first definition of a key wins."""
    defs: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.symtypes")):
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) < 2:
                    continue
                key, tokens = parts[0], parts[1:]
                if key not in defs:
                    defs[key] = tokens
    return defs


def closure(defs: dict[str, list[str]], start: str, cache: dict[str, frozenset[str]]) -> frozenset[str]:
    """Type keys reachable from *start* (iterative; cycles are legal in C)."""
    if start in cache:
        return cache[start]
    seen: set[str] = set()
    stack = [start]
    while stack:
        key = stack.pop()
        for token in defs.get(key, ()):
            if TYPE_REF.match(token) and token not in seen:
                seen.add(token)
                stack.append(token)
    result = frozenset(seen)
    cache[start] = result
    return result


def load_reference_symbols(reference: Path) -> set[str]:
    with reference.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not {"module", "symbol", "stock_crc"} <= set(reader.fieldnames or ()):
            raise SystemExit("reference TSV lacks module/symbol/stock_crc columns")
        symbols = {row["symbol"] for row in reader if row["symbol"]}
    if not symbols:
        raise SystemExit("reference TSV is empty: refusing to analyse")
    return symbols


def load_mismatches(report: Path) -> set[str]:
    found = set(MISMATCH_RE.findall(report.read_text(encoding="utf-8", errors="replace")))
    if not found:
        raise SystemExit("report lists no MISMATCH lines: nothing to analyse")
    return found


def analyse(defs, symbols, mismatching):
    """Return (candidates, deepest, uncovered, unknown_symbols)."""
    cache: dict[str, frozenset[str]] = {}
    bad_hits: dict[str, int] = defaultdict(int)
    good_hits: dict[str, int] = defaultdict(int)
    reach: dict[str, frozenset[str]] = {}
    unknown = []
    for symbol in sorted(symbols):
        if symbol not in defs:
            unknown.append(symbol)
            continue
        types = closure(defs, symbol, cache)
        reach[symbol] = types
        target = bad_hits if symbol in mismatching else good_hits
        for t in types:
            target[t] += 1
    candidates = {t: n for t, n in bad_hits.items() if good_hits.get(t, 0) == 0}
    deepest = [
        t for t in candidates
        if not (closure(defs, t, cache) & (set(candidates) - {t}))
    ]
    deepest.sort(key=lambda t: (-candidates[t], t))
    covered = {s for s, types in reach.items() if s in mismatching and types & set(candidates)}
    uncovered = sorted((mismatching & set(reach)) - covered)
    return candidates, deepest, uncovered, unknown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--symtypes", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args(argv)

    defs = load_symtypes(args.symtypes)
    if not defs:
        print("No .symtypes definitions found", file=sys.stderr)
        return 2
    symbols = load_reference_symbols(args.reference)
    mismatching = load_mismatches(args.report) & symbols
    candidates, deepest, uncovered, unknown = analyse(defs, symbols, mismatching)

    print(f"definitions={len(defs)} reference_symbols={len(symbols)} "
          f"mismatching={len(mismatching)} symbols_without_symtypes={len(unknown)}")
    print(f"types reached ONLY by mismatching symbols: {len(candidates)}")
    print(f"mismatching symbols not explained by any such type: {len(uncovered)}")
    print("\nDeepest suspect types (type, mismatching symbols reaching it):")
    for t in deepest[: args.top]:
        body = " ".join(defs[t])
        print(f"  {t}  x{candidates[t]}\n    {body[:400]}")
    if not deepest:
        print("  none: differing CRCs are not explained by a type unique to mismatching symbols")
    print("\nDiagnostic only. Not a flash approval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
