#!/usr/bin/env bash
set -euo pipefail
BOOT="${1:-boot.img}"
SOURCE="${2:-A235F_kernel_src_KernelSU.tar.gz}"
if [[ ! -f "$BOOT" ]]; then echo "HATA: boot bulunamadi: $BOOT"; exit 1; fi
if [[ ! -f "$SOURCE" ]]; then echo "HATA: kaynak arsivi bulunamadi: $SOURCE"; exit 1; fi
magic="$(head -c 8 "$BOOT")"
if [[ "$magic" != "ANDROID!" ]]; then echo "HATA: Android boot imzasi yok"; exit 1; fi
echo "Boot SHA256:"
sha256sum "$BOOT"
echo "Kaynak arsivi gzip kontrolu:"
if ! gzip -t "$SOURCE"; then
  echo "HATA: Kernel kaynak arsivi bozuk/eksik. Derleme DURDURULDU."
  exit 2
fi
echo "Kaynak arsivi tar kontrolu:"
if ! tar -tzf "$SOURCE" >/dev/null; then
  echo "HATA: Tar arsivi bozuk/eksik. Derleme DURDURULDU."
  exit 3
fi
echo "Kontroller gecti. Derleme icin kaynak incelemesi yapilabilir."
