#!/usr/bin/env python3
"""Extract the embedded stock config from an exact SM-A235F A235FXXSEEZB1 boot.img."""
import gzip, hashlib, struct, sys
from pathlib import Path

EXPECTED_BOOT = "2eacbc30868fb7d05657a3504afc2e645da04fe6000d49c56f05bfb00d7e279b"
EXPECTED_CONFIG = "967db7ebc0389dc053d40e3747056af303959d826fd028a030377e2279e4cfc1"

def main():
    boot = Path(sys.argv[1]).read_bytes()
    sha = hashlib.sha256(boot).hexdigest()
    print("Stock boot bytes:", len(boot), "SHA256:", sha)
    if sha != EXPECTED_BOOT:
        raise SystemExit("BOOT HASH MISMATCH: wrong firmware; abort")
    if boot[:8] != b"ANDROID!":
        raise SystemExit("Not an Android boot image")
    ksz = struct.unpack_from("<I", boot, 8)[0]
    psz = struct.unpack_from("<I", boot, 36)[0]
    if psz != 4096 or not 0 < ksz < 60_000_000:
        raise SystemExit("Unexpected boot image header/size")
    plain = gzip.decompress(boot[psz:psz+ksz])
    start = plain.find(b"IKCFG_ST")
    end = plain.find(b"IKCFG_ED", start)
    if start < 0 or end < 0:
        raise SystemExit("Embedded CONFIG_IKCONFIG not found")
    config = gzip.decompress(plain[start+8:end])
    config_sha = hashlib.sha256(config).hexdigest()
    if config_sha != EXPECTED_CONFIG:
        raise SystemExit("Stock kernel configuration hash mismatch")
    Path(sys.argv[2]).write_bytes(config)
    print("Verified exact stock kernel config", len(config), config_sha)

if __name__ == "__main__":
    main()
