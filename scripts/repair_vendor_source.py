#!/usr/bin/env python3
"""Targeted fixes for the SM-A235F vendor kernel tree before compiling.

Preserves SELinux, CONFIG_MODVERSIONS, CONFIG_RELOCATABLE and
the packed GSI union definition. Aborts if upstream inputs change.
"""
from pathlib import Path
import stat

root = Path.cwd()

def replace_exact(relative, old, new, expected=1):
    path = root / relative
    source = path.read_text()
    count = source.count(old)
    if count != expected:
        raise SystemExit(f"Unexpected source layout: {relative}: expected {expected}, found {count}")
    # The original firmware archive records some source files as read-only.
    # The extracted copy belongs to this job; make just this target user-writable.
    path.chmod(path.stat().st_mode | stat.S_IWUSR)
    path.write_text(source.replace(old, new))
    print(f"Patched {relative}: {count} change(s)")

# In this vendor tree .bss.rtic is currently emitted AFTER _end and after
# debug sections. It is too far away from SELinux references for ARM64's
# ADRP relocation, and would fall outside the early zeroed BSS range.
# Put the existing RTIC_BSS macro within BSS_SECTION via its supported
# BSS_FIRST_SECTIONS hook. Keep both page alignments and SELinux enabled.
replace_exact(
    "arch/arm64/kernel/vmlinux.lds.S",
    "#include <asm-generic/vmlinux.lds.h>",
    "#define BSS_FIRST_SECTIONS RTIC_BSS\n#include <asm-generic/vmlinux.lds.h>",
)
replace_exact(
    "arch/arm64/kernel/vmlinux.lds.S",
    "\n\t.bss : {\t\t\t/* bss segment\t\t*/\n         RTIC_BSS\n\t}\n}",
    "\n}",
)

# Qualcomm's genksyms parser fails on the __packed return type of
# __gsi_update_mhi_channel_scratch(), the static helper immediately before
# EXPORT_SYMBOL(gsi_write_channel_scratch). The unresolved CRC then makes
# vmlinux fail with R_AARCH64_ABS32. The union itself stays __packed, so this
# changes no type layout or calling convention.
replace_exact(
    "drivers/platform/msm/gsi/gsi.c",
    "static union __packed gsi_channel_scratch __gsi_update_mhi_channel_scratch(",
    "static union gsi_channel_scratch __gsi_update_mhi_channel_scratch(",
)

# The union TAG is already declared as packed in msm_gsi.h. Adding
# a second __packed attribute on every by-value function parameter
# is redundant and confuses older genksyms for this exported symbol.
# The memory layout and binary parameter type remain unchanged.
replace_exact(
    "drivers/platform/msm/gsi/gsi.c",
    "union __packed gsi_channel_scratch val)",
    "union gsi_channel_scratch val)",
    expected=2,
)
replace_exact(
    "include/linux/msm_gsi.h",
    "union __packed gsi_channel_scratch val",
    "union gsi_channel_scratch val",
    expected=2,
)

ldscript = (root / "arch/arm64/kernel/vmlinux.lds.S").read_text()
assert ldscript.count("RTIC_BSS") == 2, "Unexpected RTIC macro usage"
assert "BSS_FIRST_SECTIONS RTIC_BSS" in ldscript
assert "struct selinux_state selinux_state __rticdata;" in (
    root / "security/selinux/hooks.c").read_text()
assert "union __packed gsi_channel_scratch {" in (
    root / "include/linux/msm_gsi.h").read_text()
print("Source layout and security checks passed")
