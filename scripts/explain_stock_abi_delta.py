#!/usr/bin/env python3
"""Explain OEM ABI mismatches: stock-source delta versus KernelSU-hook delta.

Inputs: OEM CRC reference, stock-baseline Module.symvers, KernelSU Module.symvers.
Static comparison only; never treats a CRC match as proof of safe flashing.
"""
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

from compare_oem_crc import load_exports, load_reference


def verified_inputs(tsv, stock_sym, ksu_sym, output):
    """Reject incomplete, tampered or ambiguous inputs before classifying CRCs."""
    errors=[]
    base=ksu=entries=None
    try:
        base=load_exports(Path(stock_sym), errors)
        ksu=load_exports(Path(ksu_sym), errors)
        entries=load_reference(Path(tsv), errors)
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        errors.append(str(exc))
    if errors:
        report="SM-A235F ABI delta: FAIL CLOSED - invalid input\n"
        report+="\n".join("ERROR "+error for error in errors)+"\n"
        Path(output).parent.mkdir(parents=True,exist_ok=True)
        Path(output).write_text(report)
        raise SystemExit(report)
    return base,ksu,entries

def main():
    if len(sys.argv)!=5:
        raise SystemExit("usage: explain_stock_abi_delta.py stock_module_crc.tsv baseline.symvers ksu.symvers report.txt")
    tsv,stock_sym,ksu_sym,output = sys.argv[1:]
    base,ksu,entries=verified_inputs(tsv,stock_sym,ksu_sym,output)
    counts=defaultdict(Counter)
    rows=[]
    for module, symbols in entries.items():
        for symbol, oem in symbols.items():
            b=base.get(symbol); k=ksu.get(symbol)
            if b is None or k is None: state="missing_export"
            elif b==oem and k==oem: state="both_match_oem"
            elif b==oem and k!=oem: state="kernelSU_changed_compatible_symbol"
            elif b!=oem and k==oem: state="kernelSU_only_matches_oem"
            elif b==k: state="both_mismatch_same_crc"
            else: state="both_mismatch_different_crc"
            counts[module][state]+=1
            if state!="both_match_oem":
                rows.append((module,state,symbol,oem,b,k))
    summary=["SM-A235F OEM driver ABI delta: stock source baseline vs KernelSU direct hooks",
             "This is a static research report. Do not flash based on matching CRC alone.",
             f"Stock exports: {len(base)} | KernelSU exports: {len(ksu)}",
             ""]
    for module in sorted(counts):
        total=sum(counts[module].values())
        summary.append(f"MODULE {module}: {total} original vendor symbol references")
        for state,num in counts[module].most_common():
            summary.append(f"  {state}: {num}")
    summary+=["","DETAILS: module | state | symbol | OEM CRC | stock build CRC | KernelSU CRC"]
    def fmt(v):return "missing" if v is None else f"0x{v:08x}"
    for module,state,symbol,oem,b,k in rows:
        summary.append(f"{module}\t{state}\t{symbol}\t{fmt(oem)}\t{fmt(b)}\t{fmt(k)}")
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text("\n".join(summary)+"\n")
    print("\n".join(summary[:35]))
    if any(sum(n for k,n in c.items() if k!="both_match_oem") for c in counts.values()):
        raise SystemExit(1)

if __name__=="__main__":
    main()
