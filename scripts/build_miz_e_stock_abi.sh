#!/usr/bin/env bash
# SM-A235F Binary-E source + exact OEM IKCONFIG, isolated stock ABI experiment.
# Does not produce any approved flashable phone package.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$GITHUB_WORKSPACE/miz-e-abi-work"
MIZ_SHA='58781e08d1af2677468762062a5148c117877a71'
OEM_CFG_SHA='967db7ebc0389dc053d40e3747056af303959d826fd028a030377e2279e4cfc1'
mkdir -p "$WORK/result"
onexit() {
  local code=$?
  set +e
  for file in "$WORK/src/out/.config" "$WORK/src/out/Module.symvers" "$WORK/src/out/System.map" "$WORK/src/out/include/config/kernel.release"; do
    if test -s "$file"; then
      cp "$file" "$WORK/result/$(basename "$file")"
    fi
  done
  find "$WORK/src/out/arch/arm64/boot" -maxdepth 1 -type f -name 'Image*' -exec cp {} "$WORK/result/" \; 2>/dev/null
  printf 'exit=%s\nsource=%s\nkernel_flash_approved=false\n' "$code" "$MIZ_SHA" > "$WORK/result/STATUS.txt"
}
trap onexit EXIT
echo "Read-only pinned external source fetch; no phone operations."
git init -q "$WORK/src"
git -C "$WORK/src" remote add origin https://github.com/MizProject/MizKernel-A235F.git
git -C "$WORK/src" fetch --depth=1 --filter=blob:none origin "$MIZ_SHA"
git -C "$WORK/src" checkout -q --detach FETCH_HEAD
test "$(git -C "$WORK/src" rev-parse HEAD)" = "$MIZ_SHA"
cp "$ROOT/configs/a235fxxseezb1_stock.config" "$WORK/stock.config"
echo "$OEM_CFG_SHA  $WORK/stock.config" | sha256sum -c -
cp "$WORK/stock.config" "$WORK/src/arch/arm64/configs/vendor/a23_eur_open_mizkernel_defconfig"
# Force the exact OEM input; no KernelSU, patches or changed modversion policy.
grep -qx '# CONFIG_KPROBES is not set' "$WORK/stock.config"
grep -qx 'CONFIG_MODVERSIONS=y' "$WORK/stock.config"
grep -qx 'CONFIG_MODULE_SIG_FORCE=y' "$WORK/stock.config"
grep -qx 'CONFIG_UH=y' "$WORK/stock.config"
grep -qx 'CONFIG_RKP=y' "$WORK/stock.config"
cd "$WORK/src"
python3 miz_build.py fetch-toolchains
python3 miz_build.py check
# The Miz builder has a proven CI recipe for this E source. Reproduce it
# with the original A235FXXSEEZB1 IKCONFIG, not its custom defconfig.
python3 miz_build.py build --clean --lto keep --lld off \
  --defconfig vendor/a23_eur_open_mizkernel_defconfig \
  --localversion=-28692735-abA235FXXSEEZB1 \
  --dist-dir "$WORK/dist" 2>&1 | tee "$WORK/build.log"
test -s "$WORK/src/out/Module.symvers"
test -s "$WORK/src/out/arch/arm64/boot/Image.gz" || test -s "$WORK/src/out/arch/arm64/boot/Image"
# Ensure this test never turns into an automatically flashable release.
echo "Research-only kernel Image; no flashable boot.img created." > "$WORK/result/NO_FLASH.txt"
