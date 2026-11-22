#!/usr/bin/env bash
set -Eeuo pipefail

# Build kernel only; NEVER flash a device from CI.
SOURCE_ID="${SOURCE_ID:-1Zs5561S0TRsdFdQ_wSTqw--IoYcZiL4s}"
EXPECTED_SHA256="bc4b43d689e531e035ff8d4b08eec232bd36ce245f9eeb4c878c7d5ff141e10e"
WORK_DIR="${WORK_DIR:-$PWD/stock-abi-work}"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

if [[ -n "${SOURCE_ARCHIVE:-}" && -s "${SOURCE_ARCHIVE}" ]]; then
    cp "$SOURCE_ARCHIVE" source.tar.gz
else
    command -v gdown >/dev/null || { echo 'gdown missing'; exit 10; }
    gdown --fuzzy "https://drive.google.com/file/d/${SOURCE_ID}/view" -O source.tar.gz
fi

echo "${EXPECTED_SHA256}  source.tar.gz" | sha256sum --check -
# Exact OEM IKCONFIG has been verified against uploaded original boot.
# Bundled in this GitHub repository: no private boot.img download required.
cp "$GITHUB_WORKSPACE/configs/a235fxxseezb1_stock.config" stock.config
echo '967db7ebc0389dc053d40e3747056af303959d826fd028a030377e2279e4cfc1  stock.config' | sha256sum --check -

tar -tzf source.tar.gz > "$WORK_DIR/archive-files.txt"
grep -qx 'kernel_src/Makefile' "$WORK_DIR/archive-files.txt"
mkdir -p unpack
tar -xzf source.tar.gz -C unpack --no-same-owner
cd unpack/kernel_src
python3 "$GITHUB_WORKSPACE/scripts/repair_vendor_source.py"
# Samsung FIVE references a private driver header as an angle-bracket include.
# Resolve the *same* local header via a relative path, preserving the types.
FIVE_HEADER="security/samsung/five/five_porting.h"
test -f drivers/block/loop.h || { echo "FIVE dependency driver header missing" >&2; exit 42; }
python3 - "$FIVE_HEADER" <<'PY'
import re, stat, sys
from pathlib import Path
path=Path(sys.argv[1])
s=path.read_text()
pattern=r'(?m)^[ \t]*#[ \t]*include[ \t]*[<"]drivers/block/loop\.h[>"]'
patched,count=re.subn(pattern, '#include "../../../drivers/block/loop.h"',s)
if count != 1:
    print("Unexpected FIVE header include count:", count)
    print("Source references:",[line for line in s.splitlines() if "drivers/block/loop.h" in line])
    raise SystemExit(43)
path.chmod(path.stat().st_mode | stat.S_IWUSR)
path.write_text(patched)
print("FIVE security source header path fixed; original driver header reused")
PY
# The source ships both dynamic kprobes and legacy direct hooks.
# CONFIG_KPROBES=y means hook variables are not defined by KernelSU.
# Disable only the duplicate direct-call sites; keep dynamic kprobe support.
for source_file in fs/read_write.c fs/exec.c drivers/input/input.c; do
    count="$(grep -c '^#ifdef CONFIG_KSU$' "$source_file")"
    if [[ "$count" -ne 2 ]]; then
        echo "Unexpected direct-hook layout in $source_file: $count" >&2
        exit 21
    fi
    sed -i 's/^#ifdef CONFIG_KSU$/#if defined(CONFIG_KSU) \&\& !defined(CONFIG_KPROBES)/' "$source_file"
done
# Preserve CONFIG_MODVERSIONS for vendor modules, but use GNU ld.bfd
# to handle ABS32 symbol CRC relocations rejected by ld.lld.
[[ -L drivers/kernelsu && -f drivers/kernelsu/Makefile ]] || { echo 'KernelSU integration missing'; exit 12; }
grep -q '^CONFIG_KSU=y' arch/arm64/configs/vendor/a23_eur_open_defconfig || { echo 'KernelSU not enabled'; exit 13; }

export PATH="/usr/lib/llvm-14/bin:$PATH"
for cmd in clang-14 ld.lld llvm-ar llvm-nm llvm-objcopy llvm-objdump llvm-readelf aarch64-linux-gnu-gcc aarch64-linux-gnu-ld arm-linux-gnueabi-gcc bison flex bc make; do
    command -v "$cmd" >/dev/null || { echo "Tool missing: $cmd"; exit 14; }
done
mkdir -p out
args=(ARCH=arm64 O="$PWD/out" LLVM=1 CC=clang-14 LD=aarch64-linux-gnu-ld HOSTCC=gcc HOSTCXX=g++ CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- CLANG_TRIPLE=aarch64-linux-gnu- DTC_EXT="$PWD/tools/dtc" CONFIG_SECTION_MISMATCH_WARN_ONLY=y LOCALVERSION=-28692735-abA235FXXSEEZB1)
make "${args[@]}" vendor/a23_eur_open_defconfig 2>&1 | tee "$WORK_DIR/config.log"
cp "$WORK_DIR/stock.config" out/.config
mkdir -p "$WORK_DIR/result"
cp "$WORK_DIR/stock.config" "$WORK_DIR/result/stock.config"
# Two separately labelled RESEARCH builds. Never flash either from CI.
PROFILE="${KERNEL_PROFILE:-stock_baseline}"
case "$PROFILE" in
    stock_baseline|stock_ksu_directhooks) ;;
    *) echo "Unknown KERNEL_PROFILE: $PROFILE" >&2; exit 30 ;;
esac
echo "$PROFILE" > "$WORK_DIR/kernel_profile.txt"
# scripts/config edits the generated config, NOT the source defconfig.
# olddefconfig re-evaluates dependencies, particularly SELinux dependent flags.
# Match OEM base: KPROBES is disabled in stock kernel, avoiding its ABI change.
# Trust the original firmware's PUBLIC X.509 certificate for its existing signed
# Wi-Fi and rdbg modules. This does not copy any private signing key.
cp "$GITHUB_WORKSPACE/certs/a235fxxseezb1_oem_trusted.pem" certs/a235fxxseezb1_oem_trusted.pem
openssl x509 -in certs/a235fxxseezb1_oem_trusted.pem -noout -serial | tee "$WORK_DIR/result/OEM-cert-serial.txt"
grep -qi '7C2B781205C5CF85AA1BCD9242CD1E4E4FD12AFF' "$WORK_DIR/result/OEM-cert-serial.txt" || { echo 'OEM cert mismatch' >&2; exit 44; }
./scripts/config --file out/.config --disable LOCALVERSION_AUTO --disable KPROBES \
    --set-str SYSTEM_TRUSTED_KEYS certs/a235fxxseezb1_oem_trusted.pem
if [[ "$PROFILE" == "stock_baseline" ]]; then
    ./scripts/config --file out/.config --disable KSU
else
    # Use in-tree KernelSU direct hooks instead of kprobe hook injection.
    ./scripts/config --file out/.config --enable KSU \
        --set-val PANIC_TIMEOUT 0 --disable PANIC_ON_OOPS
fi
make "${args[@]}" olddefconfig 2>&1 | tee -a "$WORK_DIR/config.log"
# Save full delta: even the stock baseline may lose proprietary OEM symbols.
python3 "$GITHUB_WORKSPACE/scripts/compare_kernel_config.py" "$WORK_DIR/stock.config" out/.config "$WORK_DIR/result/config-diff.txt"
grep -qx 'CONFIG_MODVERSIONS=y' out/.config || { echo 'MODVERSIONS missing' >&2; exit 30; }
grep -qx 'CONFIG_SECURITY_SELINUX=y' out/.config || { echo 'SELinux disabled unexpectedly' >&2; exit 33; }
grep -qx '# CONFIG_KPROBES is not set' out/.config || { echo 'KPROBES must match stock: n' >&2; exit 34; }
if [[ "$PROFILE" == "stock_baseline" ]]; then
    grep -qx '# CONFIG_KSU is not set' out/.config || { echo 'Baseline KSU should be disabled' >&2; exit 31; }
else
    grep -qx 'CONFIG_KSU=y' out/.config || { echo 'KernelSU enable lost' >&2; exit 31; }
    grep -qx 'CONFIG_PANIC_TIMEOUT=0' out/.config || { echo 'Panic timeout not 0' >&2; exit 32; }
fi
# Keep uname -r identical to the stock firmware to avoid obvious
# vermagic mismatch with vendor modules. Symbol CRC/ABI still need validation.
EXPECTED_RELEASE='4.19.157-perf-28692735-abA235FXXSEEZB1'
ACTUAL_RELEASE="$(make "${args[@]}" --no-print-directory -s kernelrelease | tail -n 1)"
echo "Kernel release: $ACTUAL_RELEASE (expected: $EXPECTED_RELEASE)"
[[ "$ACTUAL_RELEASE" == "$EXPECTED_RELEASE" ]] || { echo 'Kernel release mismatch' >&2; exit 37; }
cp out/.config "$WORK_DIR/kernel-prebuild.config"
echo "Profile verified: $PROFILE" | tee -a "$WORK_DIR/config.log"
# Clang 14 emits unused-but-set-variable as -Werror in legacy Qualcomm audio sources.
# Demote ONLY this diagnostic; preserve all other compiler errors and driver behavior.
make "${args[@]}" KCFLAGS="-Wno-error=unused-but-set-variable" -j"${JOBS:-4}" 2>&1 | tee "$WORK_DIR/build.log"
mkdir -p "$WORK_DIR/result"
cp out/.config "$WORK_DIR/result/kernel.config"
find out/arch/arm64/boot -maxdepth 1 -type f \( -name 'Image' -o -name 'Image.gz' -o -name '*-dtb' \) -exec cp -v {} "$WORK_DIR/result/" \;
# Module ABI diagnostics: prepare CRC symbol table and built modules for
# comparison against the actual vendor qca_cld3_wlan.ko / rdbg.ko.
test -s out/Module.symvers || { echo 'Module.symvers missing' >&2; exit 38; }
cp out/Module.symvers "$WORK_DIR/result/"
test -s out/System.map || { echo 'System.map missing' >&2; exit 39; }
cp out/System.map "$WORK_DIR/result/"
mkdir -p "$WORK_DIR/result/modules"
find out -type f -name '*.ko' -exec cp -v {} "$WORK_DIR/result/modules/" \;
printf '%s\n' 'NOTE: Vendor .ko files are NOT bundled, therefore ABI is not yet verified.' > "$WORK_DIR/result/ABI-STATUS.txt"
ls -lah "$WORK_DIR/result"
test -s "$WORK_DIR/result/Image" || test -s "$WORK_DIR/result/Image.gz"
# Hash regular files recursively. The result/modules/ directory must not be
# passed to sha256sum as a file (that would fail the completed build job).
( cd "$WORK_DIR/result" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 -r sha256sum ) | tee "$WORK_DIR/result/SHA256SUMS"
echo "Stock-reference ABI research outputs. NOT a flashable boot.img."
