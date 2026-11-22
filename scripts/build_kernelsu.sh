#!/usr/bin/env bash
set -Eeuo pipefail

# Build kernel only; NEVER flash a device from CI.
SOURCE_ID="${SOURCE_ID:-1Zs5561S0TRsdFdQ_wSTqw--IoYcZiL4s}"
EXPECTED_SHA256="bc4b43d689e531e035ff8d4b08eec232bd36ce245f9eeb4c878c7d5ff141e10e"
WORK_DIR="${WORK_DIR:-$PWD/a23-build}"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

if [[ -n "${SOURCE_ARCHIVE:-}" && -s "${SOURCE_ARCHIVE}" ]]; then
    cp "$SOURCE_ARCHIVE" source.tar.gz
else
    command -v gdown >/dev/null || { echo 'gdown missing'; exit 10; }
    gdown --fuzzy "https://drive.google.com/file/d/${SOURCE_ID}/view" -O source.tar.gz
fi

echo "${EXPECTED_SHA256}  source.tar.gz" | sha256sum --check -
tar -tzf source.tar.gz > "$WORK_DIR/archive-files.txt"
grep -qx 'kernel_src/Makefile' "$WORK_DIR/archive-files.txt"
mkdir -p unpack
tar -xzf source.tar.gz -C unpack --no-same-owner
cd unpack/kernel_src
python3 "$GITHUB_WORKSPACE/scripts/repair_vendor_source.py"
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
# Two separately labelled RESEARCH builds. Never flash either from CI.
PROFILE="${KERNEL_PROFILE:-enforcing_panic0}"
case "$PROFILE" in
    enforcing_panic0|selinux_off_experimental) ;;
    *) echo "Unknown KERNEL_PROFILE: $PROFILE" >&2; exit 30 ;;
esac
echo "$PROFILE" > "$WORK_DIR/kernel_profile.txt"
# scripts/config edits the generated config, NOT the source defconfig.
# olddefconfig re-evaluates dependencies, particularly SELinux dependent flags.
./scripts/config --file out/.config --set-val PANIC_TIMEOUT 0 --disable PANIC_ON_OOPS \
    --disable LOCALVERSION_AUTO
if [[ "$PROFILE" == "enforcing_panic0" ]]; then
    ./scripts/config --file out/.config --enable SECURITY_SELINUX --enable DEFAULT_SECURITY_SELINUX
else
    ./scripts/config --file out/.config --disable SECURITY_SELINUX \
        --disable DEFAULT_SECURITY_SELINUX --enable DEFAULT_SECURITY_DAC \
        --set-str DEFAULT_SECURITY dac
fi
make "${args[@]}" olddefconfig 2>&1 | tee -a "$WORK_DIR/config.log"
grep -qx 'CONFIG_KSU=y' out/.config || { echo 'KernelSU lost after olddefconfig' >&2; exit 31; }
grep -qx 'CONFIG_PANIC_TIMEOUT=0' out/.config || { echo 'PANIC_TIMEOUT did not apply' >&2; exit 32; }
if [[ "$PROFILE" == "enforcing_panic0" ]]; then
    grep -qx 'CONFIG_SECURITY_SELINUX=y' out/.config || { echo 'SELinux not enabled' >&2; exit 33; }
else
    grep -qx '# CONFIG_SECURITY_SELINUX is not set' out/.config || { echo 'SELinux not disabled' >&2; exit 34; }
    # Kconfig can select the DAC fallback even when DEFAULT_SECURITY is empty.
    # Verify that SELinux is neither compiled in nor selected as the default.
    echo 'SELinux-off security options:'
    grep -E '^(CONFIG_DEFAULT_SECURITY|# CONFIG_DEFAULT_SECURITY|CONFIG_SECURITY_SELINUX|# CONFIG_SECURITY_SELINUX)' out/.config || true
    if grep -Eq '^CONFIG_DEFAULT_SECURITY="selinux"$|^CONFIG_DEFAULT_SECURITY_SELINUX=y$' out/.config; then
        echo 'Unexpected SELinux default security' >&2; exit 35
    fi
    if grep -qx 'CONFIG_SECURITY_SELINUX_DEVELOP=y' out/.config; then
        echo 'Stale SELinux-dependent config option' >&2; exit 36
    fi
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
echo "Build outputs ready for validation; this is NOT a flashable boot.img."
