#!/usr/bin/env python3
"""Extract only public module ABI metadata from proprietary vendor .ko binaries."""
from pathlib import Path
import hashlib
import struct
import sys
from check_vendor_abi import sections

def main():
    target=Path(sys.argv[1])
    output=Path(sys.argv[2])
    entries=[]
    metadata=[]
    for name in ("qca_cld3_wlan.ko","rdbg.ko"):
        file=target/name
        data=file.read_bytes()
        sec=sections(file)
        info={}
        for item in sec.get(".modinfo",b"").split(b"\0"):
            if b"=" in item:
                k,v=item.split(b"=",1)
                info[k.decode(errors="replace")]=v.decode(errors="replace")
        versions=sec.get("__versions",b"")
        if not versions or len(versions)%64:
            raise RuntimeError("No valid __versions: "+name)
        metadata.append((name,len(data),hashlib.sha256(data).hexdigest(),info.get("vermagic","")))
        for i in range(0,len(versions),64):
            crc=struct.unpack_from("<Q",versions,i)[0]&0xffffffff
            symbol=versions[i+8:i+64].split(b"\0",1)[0].decode(errors="replace")
            if symbol:
                entries.append((name,symbol,crc))
    entries.sort()
    output.parent.mkdir(exist_ok=True,parents=True)
    output.write_text("module\tsymbol\tstock_crc\n"+"".join(f"{n}\t{s}\t0x{crc:08x}\n" for n,s,crc in entries))
    with (output.parent/"vendor_module_metadata.txt").open("w") as f:
        for name,size,sha,vermagic in metadata:
            f.write(f"{name}: size={size} SHA256={sha} vermagic={vermagic}\n")
    print("REFERENCE_CRC_COUNT",len(entries),"MODULES",len(metadata))

if __name__=="__main__":
    main()
