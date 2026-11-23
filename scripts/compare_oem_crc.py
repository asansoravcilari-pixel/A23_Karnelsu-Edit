#!/usr/bin/env python3
"""Compare a kernel Module.symvers with verified stock Samsung .ko CRC metadata."""
import csv
from collections import defaultdict
from pathlib import Path
import sys

if len(sys.argv)!=4:
    raise SystemExit("usage: compare_oem_crc.py stock_module_crc.tsv Module.symvers report.txt")
reference, symfile, report=map(Path,sys.argv[1:])
new={}
for line in symfile.read_text(errors="replace").splitlines():
    fields=line.split()
    if len(fields)>1:
        try:new[fields[1]]=int(fields[0],16)&0xffffffff
        except ValueError:pass
if not new:
    raise SystemExit("Empty or invalid Module.symvers")
out=defaultdict(lambda:{"match":0,"mismatch":[],"missing":[]})
reference_rows=0
for row in csv.DictReader(reference.open(),delimiter="\t"):
    reference_rows+=1
    module,symbol=row["module"],row["symbol"]
    crc=int(row["stock_crc"],16)
    if symbol not in new:out[module]["missing"].append(symbol)
    elif new[symbol]!=crc:out[module]["mismatch"].append((symbol,crc,new[symbol]))
    else:out[module]["match"]+=1
if reference_rows == 0:
    raise SystemExit("Empty OEM CRC reference: refusing false ABI success")
lines=["A235FXXSEEZB1 OEM module ABI static comparison",f"New export symbols: {len(new)}"]
failed=False
for module in sorted(out):
    a=out[module];lines.append(f"MODULE {module}: match={a['match']} mismatch={len(a['mismatch'])} missing={len(a['missing'])}")
    for symbol,stock,rebuilt in a["mismatch"]:
        lines.append(f"  MISMATCH {symbol}: OEM=0x{stock:08x} rebuilt=0x{rebuilt:08x}")
    for symbol in a["missing"]:
        lines.append(f"  MISSING {symbol}")
    failed|=bool(a["mismatch"] or a["missing"])
lines.append("RESULT: STATIC ABI MISMATCH — NEVER FLASH" if failed else
             "RESULT: STATIC CRC MATCH; SIGNING, AVB, AND DEVICE BOOT STILL UNVERIFIED")
lines.append("CRC checks are necessary but not sufficient to guarantee device stability.")
report.parent.mkdir(parents=True,exist_ok=True)
report.write_text("\n".join(lines)+"\n")
print("\n".join(lines[:80]))
if failed:raise SystemExit(1)
