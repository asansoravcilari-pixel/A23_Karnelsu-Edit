#!/usr/bin/env python3
"""Fail-closed OEM module CRC gate for Samsung SM-A235F A235FXXSEEZB1.

CRC match is necessary but NOT sufficient for flashing: Samsung OEM module
signature trust and actual device boot remain independent gates.
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

# Counts from original, verified A235FXXSEEZB1 vendor modules.
EXPECTED_COUNTS = {"qca_cld3_wlan.ko": 408, "rdbg.ko": 34}
# SHA-256 of the text-only OEM CRC reference exported in Actions run 45077059624.
# Counts alone cannot detect replacing an import with a different symbol.
EXPECTED_REFERENCE_SHA256 = "8eb9e40c752dd0bdc2c0ada636a402516841adcd1348a706b4e3dbfcf3f1228a"
CRC_RE = re.compile(r"0x[0-9a-fA-F]{1,16}\Z")


def check_crc(text: str) -> int:
    if not CRC_RE.fullmatch(text or ""):
        raise ValueError("invalid hexadecimal CRC: " + repr(text))
    crc = int(text, 16)
    if crc > 0xFFFFFFFF:
        raise ValueError("CRC exceeds 32-bit width: " + repr(text))
    return crc


def load_exports(symfile: Path, errors: list[str]) -> dict[str, int]:
    exports: dict[str, int] = {}
    for number, line in enumerate(symfile.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) < 2:
            errors.append(f"Module.symvers line {number}: malformed entry")
            continue
        try:
            crc = check_crc(fields[0])
        except ValueError as exc:
            errors.append(f"Module.symvers line {number}: {exc}")
            continue
        symbol = fields[1]
        if symbol in exports:
            errors.append(f"Module.symvers line {number}: duplicate exported symbol {symbol}")
            continue
        exports[symbol] = crc
    if not exports:
        errors.append("Module.symvers contains no valid exports")
    return exports


def load_reference(reference: Path, errors: list[str]) -> dict[str, dict[str, int]]:
    entries: dict[str, dict[str, int]] = defaultdict(dict)
    digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    if digest != EXPECTED_REFERENCE_SHA256:
        errors.append(
            "OEM reference SHA-256 mismatch: expected "
            f"{EXPECTED_REFERENCE_SHA256}, got {digest}"
        )
    with reference.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"module", "symbol", "stock_crc"}
        if not reader.fieldnames or set(reader.fieldnames) != required:
            errors.append("OEM reference TSV header must be module, symbol, stock_crc")
            return entries
        for number, row in enumerate(reader, 2):
            if None in row or any(row.get(k) is None for k in required):
                errors.append(f"OEM reference line {number}: invalid column count")
                continue
            module, symbol, encoded = (row[k].strip() for k in ("module", "symbol", "stock_crc"))
            if module not in EXPECTED_COUNTS:
                errors.append(f"OEM reference line {number}: unexpected module {module!r}")
                continue
            if not symbol:
                errors.append(f"OEM reference line {number}: empty symbol")
                continue
            try:
                crc = check_crc(encoded)
            except ValueError as exc:
                errors.append(f"OEM reference line {number}: {exc}")
                continue
            if symbol in entries[module]:
                errors.append(f"OEM reference line {number}: duplicated import {module}:{symbol}")
                continue
            entries[module][symbol] = crc
    for module, count in EXPECTED_COUNTS.items():
        found = len(entries[module])
        if found != count:
            errors.append(f"OEM reference {module}: expected {count} unique imports, got {found}")
    return entries


def compare(reference: Path, symfile: Path, report: Path) -> bool:
    errors: list[str] = []
    exports = load_exports(symfile, errors)
    entries = load_reference(reference, errors)
    lines = [
        "SM-A235F A235FXXSEEZB1 OEM CRC ABI gate",
        f"Export symbols: {len(exports)}",
        "Fail-closed: CRC match alone NEVER approves flash; Samsung OEM signatures and device boot unverified.",
    ]
    mismatches = 0
    missing = 0
    for module in EXPECTED_COUNTS:
        matches = 0
        local_mismatches = []
        local_missing = []
        for symbol, stock in entries[module].items():
            if symbol not in exports:
                local_missing.append(symbol)
            elif exports[symbol] != stock:
                local_mismatches.append((symbol, stock, exports[symbol]))
            else:
                matches += 1
        mismatches += len(local_mismatches)
        missing += len(local_missing)
        lines.append(f"MODULE {module}: match={matches} mismatch={len(local_mismatches)} missing={len(local_missing)}")
        for symbol, expected, actual in local_mismatches:
            lines.append(f"  MISMATCH {symbol}: OEM=0x{expected:08x} rebuilt=0x{actual:08x}")
        for symbol in local_missing:
            lines.append(f"  MISSING {symbol}")
    for error in errors:
        lines.append("ERROR " + error)
    success = not errors and not mismatches and not missing
    lines.append(
        "RESULT: STATIC CRC MATCH ONLY; OEM SIGNATURE, AVB, DEVICE BOOT STILL UNVERIFIED"
        if success else "RESULT: FAIL CLOSED — DO NOT FLASH"
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:80]))
    return success


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: compare_oem_crc.py stock_module_crc.tsv Module.symvers report.txt", file=sys.stderr)
        return 2
    try:
        return 0 if compare(*(Path(item) for item in sys.argv[1:])) else 1
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        print(f"FAIL CLOSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
