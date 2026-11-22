#!/usr/bin/env python3
"""Compare exact IKCONFIG against effective Kconfig after olddefconfig."""
from pathlib import Path
import sys

def read(path):
    out={}
    for line in Path(path).read_text(errors="replace").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key,value=line.split("=",1)
            out[key]=value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            out[line[2:-11]]="n"
    return out

stock, built = read(sys.argv[1]),read(sys.argv[2])
diffs=[(k,stock.get(k,"<missing>"),built.get(k,"<missing>"))
       for k in sorted(set(stock)|set(built)) if stock.get(k)!=built.get(k)]
lines=["Stock firmware config vs generated config: "+str(len(diffs))+" different keys"]
lines += [f"{k}: STOCK={a} GENERATED={b}" for k,a,b in diffs]
lines += ["","WARNING: matching release string does NOT prove module ABI compatibility."]
Path(sys.argv[3]).write_text("\n".join(lines)+"\n")
print("\n".join(lines[:110]))
