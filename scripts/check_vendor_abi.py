#!/usr/bin/env python3
"""Read-only ABI comparison: Samsung A235F vendor .ko vs new Module.symvers."""
import sys,struct
from pathlib import Path

EXPECTED="4.19.157-perf-28692735-abA235FXXSEEZB1"

def sections(path):
    d=Path(path).read_bytes()
    if len(d)<64 or d[:4]!=b"\x7fELF" or d[4]!=2 or d[5]!=1 or struct.unpack_from("<H",d,18)[0]!=183:
        raise ValueError("not AArch64 ELF64 LE")
    shoff=struct.unpack_from("<Q",d,40)[0]
    ent,num,stridx=struct.unpack_from("<HHH",d,58)
    if not ent or not num or stridx>=num or shoff+ent*num>len(d):
        raise ValueError("invalid ELF sections")
    items=[]
    for i in range(num):
        n,t,fl,ad,off,size,link,info,al,es=struct.unpack_from("<IIQQQQIIQQ",d,shoff+i*ent)
        if t!=8 and off+size>len(d):raise ValueError("truncated ELF section")
        items.append((n,t,off,size))
    no,t,off,sz=items[stridx]
    names=d[off:off+sz]; result={}
    for no,t,off,sz in items:
        if no>=len(names) or t==8:continue
        nm=names[no:].split(b"\0",1)[0].decode(errors="replace")
        result[nm]=d[off:off+sz]
    return result

def main():
    sympath=Path(sys.argv[1]); root=Path(sys.argv[2])
    syms={}
    for line in sympath.read_text(errors="replace").splitlines():
        x=line.split()
        if len(x)>1:
            try: syms[x[1]]=int(x[0],16)&0xffffffff
            except ValueError: pass
    modules=sorted(root.rglob("*.ko"))
    print("SM-A235F vendor ABI audit / Samsung A235FXXSEEZB1")
    print("Vendor modules:",[p.name for p in modules])
    print("New exported symbols:",len(syms))
    if not syms or not modules:
        print("RESULT: INCOMPLETE (Module.symvers or vendor modules missing)")
        return 2
    failure=False; uncertain=False
    for p in modules:
        print("\nMODULE:",p)
        try:
            sec=sections(p)
            meta={}
            for x in sec.get(".modinfo",b"").split(b"\0"):
                if b"=" in x:
                    k,v=x.split(b"=",1);meta[k.decode(errors="replace")]=v.decode(errors="replace")
            vm=meta.get("vermagic","<missing>")
            print("  vermagic:",vm)
            if vm.split(" ",1)[0]!=EXPECTED:
                print("  FAIL: release mismatch"); failure=True
            vs=sec.get("__versions",b"")
            if not vs or len(vs)%64:
                print("  UNKNOWN: no recognized __versions section");uncertain=True;continue
            known=0;missing=[];mismatch=[]
            for i in range(0,len(vs),64):
                crc=struct.unpack_from("<Q",vs,i)[0]&0xffffffff
                name=vs[i+8:i+64].split(b"\0",1)[0].decode(errors="replace")
                if not name:continue
                if name not in syms:missing.append(name)
                elif syms[name]!=crc:mismatch.append((name,crc,syms[name]))
                else:known+=1
            print("  CRC matched:",known,"mismatched:",len(mismatch),"unresolved:",len(missing))
            for name,old,new in mismatch[:25]:
                print(f"  CRC FAIL {name}: vendor={old:08x} new={new:08x}")
            if missing:print("  UNKNOWN external symbols:",", ".join(missing[:20]));uncertain=True
            if mismatch:failure=True
        except Exception as exc:
            print("  ERROR:",exc);uncertain=True
    if not any(x.name=="qca_cld3_wlan.ko" for x in modules):
        print("  UNKNOWN: stock Wi-Fi module missing");uncertain=True
    if not any(x.name=="rdbg.ko" for x in modules):
        print("  UNKNOWN: stock rdbg.ko missing");uncertain=True
    print("\nRESULT:", "FAIL - ABI mismatch" if failure else "PARTIAL - more evidence required" if uncertain else "STATIC PASS - device boot not proven")
    print("SELinux remains enforcing; no flash or module load was performed.")
    return 1 if failure else 2 if uncertain else 0

if __name__=="__main__":
    sys.exit(main())
