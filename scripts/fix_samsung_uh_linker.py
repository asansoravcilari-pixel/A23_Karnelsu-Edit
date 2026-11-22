#!/usr/bin/env python3
"""Remove the *duplicate* end-of-image ARM64 page table placement only for UH+RKP.

The OEM asm-generic/vmlinux.lds.h places PG_IDMAP/PG_SWAP (and optional PG_TRAMP,
PG_RESERVED) in the protected UH .uh_ro section when CONFIG_RKP && CONFIG_UH.
The OEM arch/arm64/kernel/vmlinux.lds.S also places the same symbols after BSS
unconditionally, leading to two conflicting allocations with GNU ld.bfd.

Never turn off UH/RKP/SELinux or modify table sizing expressions.
"""
from pathlib import Path
import re
import stat

arm=Path("arch/arm64/kernel/vmlinux.lds.S")
generic=Path("include/asm-generic/vmlinux.lds.h")
a=arm.read_text()
g=generic.read_text()
# Check OEM source still matches the verified Samsung layout.
for expected in (
    "#ifdef CONFIG_RKP",
    "#define RKP_RO_DATA",
    "PG_IDMAP",
    "PG_SWAP",
    "#ifdef CONFIG_UH",
    "RKP_RO_DATA\t/* Read only after init */",
):
    if expected not in g:
        raise SystemExit("Unexpected asm-generic UH/RKP linker layout: "+expected)
pattern=re.compile(
    r"(\tBSS_SECTION\(0, 0, 0\)\n\n)"
    r"(\t\. = ALIGN\(PAGE_SIZE\);\n\tidmap_pg_dir = \.;\n"
    r"[\s\S]*?"
    r"\tswapper_pg_dir = \.;\n\t\. \+= SWAPPER_DIR_SIZE;\n"
    r"\tswapper_pg_end = \.;\n)",
)
if len(pattern.findall(a)) != 1:
    raise SystemExit("Expected exactly one ARM64 end-of-image page table block")
guard=(
    "#if !defined(CONFIG_RKP) || !defined(CONFIG_UH)\n"
    "/* UH+RKP already places these identical page tables in protected .uh_ro. */\n"
)
a,count=pattern.subn(lambda m:m.group(1)+guard+m.group(2)+"#endif\n",a)
if count!=1 or a.count("idmap_pg_dir = .;")!=1 or a.count("swapper_pg_dir = .;")!=1:
    raise SystemExit("Unexpected linker patch result")
arm.chmod(arm.stat().st_mode | stat.S_IWUSR)
arm.write_text(a)
print("Conditionalized duplicate ARM64 page tables; UH/RKP secure placement preserved")
