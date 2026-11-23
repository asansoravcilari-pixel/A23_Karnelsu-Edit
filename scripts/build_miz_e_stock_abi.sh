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
# Research-only trust test: keep Samsung's forced module signature checks enabled,
# but also trust the publicly extracted OEM signing certificate.
OEM_CERT=certs/a235fxxseezb1_oem_trusted.pem
cp "$ROOT/$OEM_CERT" "$WORK/src/$OEM_CERT"
openssl x509 -in "$WORK/src/$OEM_CERT" -noout -serial > "$WORK/result/oem-cert-identity.txt"
grep -qi '7C2B781205C5CF85AA1BCD9242CD1E4E4FD12AFF' "$WORK/result/oem-cert-identity.txt"
python3 - "$WORK/src/arch/arm64/configs/vendor/a23_eur_open_mizkernel_defconfig" "$OEM_CERT" <<'PY'
from pathlib import Path
import sys
cfg, name = Path(sys.argv[1]), sys.argv[2]
data = cfg.read_text()
expected='CONFIG_SYSTEM_TRUSTED_KEYS=""'
if data.count(expected) != 1:
    raise SystemExit("Unexpected stock SYSTEM_TRUSTED_KEYS config; fail closed")
cfg.write_text(data.replace(expected, f'CONFIG_SYSTEM_TRUSTED_KEYS="{name}"'))
print("OEM public certificate added as additional kernel trust anchor; original forced signature checks preserved")
PY
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
# Verify the FINAL generated config and check the actual raw kernel image
# contains the complete OEM X509 DER certificate, not just a file on disk.
cp "$WORK/src/out/.config" "$WORK/result/kernel.config"
grep -qx 'CONFIG_MODULE_SIG_FORCE=y' "$WORK/result/kernel.config"
grep -qx 'CONFIG_MODVERSIONS=y' "$WORK/result/kernel.config"
grep -qx 'CONFIG_SECURITY_SELINUX=y' "$WORK/result/kernel.config"
grep -qx 'CONFIG_RKP=y' "$WORK/result/kernel.config"
grep -qx 'CONFIG_UH=y' "$WORK/result/kernel.config"
grep -qx 'CONFIG_SYSTEM_TRUSTED_KEYS="certs/a235fxxseezb1_oem_trusted.pem"' "$WORK/result/kernel.config"
python3 - "$WORK/src/out/arch/arm64/boot/Image" "$WORK/src/$OEM_CERT" <<'PY'
import subprocess, sys
from pathlib import Path
image=Path(sys.argv[1]).read_bytes()
der=subprocess.check_output(['openssl','x509','-in',sys.argv[2],'-outform','DER'])
if der not in image:
    raise SystemExit("FAIL CLOSED: OEM public X509 DER not found in built Image")
print(f"OEM DER embedded in raw Image: yes; length={len(der)}")
PY
printf 'OEM DER embedded=yes\nOEM module signature verification still requires a live device test\n' > "$WORK/result/oem-cert-trust-STATIC-ONLY.txt"
test -s "$WORK/src/out/arch/arm64/boot/Image.gz" || test -s "$WORK/src/out/arch/arm64/boot/Image"
# Ensure this test never turns into an automatically flashable release.
echo "Research-only kernel Image; no flashable boot.img created." > "$WORK/result/NO_FLASH.txt"
