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
args=(ARCH=arm64 O="$PWD/out" LLVM=1 CC=clang-14 LD=aarch64-linux-gnu-ld HOSTCC=gcc HOSTCXX=g++ CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- CLANG_TRIPLE=aarch64-linux-gnu- DTC_EXT="$PWD/tools/dtc" CONFIG_SECTION_MISMATCH_WARN_ONLY=y)
make "${args[@]}" vendor/a23_eur_open_defconfig 2>&1 | tee "$WORK_DIR/config.log"
grep -q '^CONFIG_KSU=y' out/.config || { echo 'KernelSU was lost in config'; exit 15; }
# Clang 14 emits unused-but-set-variable as -Werror in legacy Qualcomm audio sources.
# Demote ONLY this diagnostic; preserve all other compiler errors and driver behavior.
make "${args[@]}" KCFLAGS="-Wno-error=unused-but-set-variable" -j"${JOBS:-4}" 2>&1 | tee "$WORK_DIR/build.log"
mkdir -p "$WORK_DIR/result"
cp out/.config "$WORK_DIR/result/kernel.config"
find out/arch/arm64/boot -maxdepth 1 -type f \( -name 'Image' -o -name 'Image.gz' -o -name '*-dtb' \) -exec cp -v {} "$WORK_DIR/result/" \;
ls -lah "$WORK_DIR/result"
test -s "$WORK_DIR/result/Image" || test -s "$WORK_DIR/result/Image.gz"
sha256sum "$WORK_DIR"/result/* | tee "$WORK_DIR/result/SHA256SUMS"
echo "Build outputs ready for validation; this is NOT a flashable boot.img."
