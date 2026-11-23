# SM-A235F B14 — Snapdragon LLVM 10.0.7 adayının kaynak ve güven kontrolü (23 Kasım 2026)

> **Yalnızca araştırma kaydıdır.** Bu dosya OEM ABI eşitliği, imzalı vendor modülü kabulü, güvenli boot veya flash izni sağlamaz. Haricî derleyici **çalıştırılmadı** ve **resmî paket olarak doğrulanmadı**.

## Yeni aday: üçüncü taraf SDClang kopyası

- Depo: https://github.com/sticpaper/Snapdragon-LLVM-ARM-Compiler-10.0.7-for-Android-NDK
- Sabit commit: `a16fec82a8deaf8f742ea54f8de98c021af200d4` (6 Ocak 2024, **imzasız** commit).
- `RELEASE_NOTES` dosyası “Snapdragon LLVM ARM C/C++ Toolchain 10.0.7” sürümünü tanımlıyor.
- `bin/clang`: GitHub içerik API'sinde **96.194.392 bayt**, Git **blob SHA-1** `5b0eb56499f8d72312fb5f43df1950ad8e8b8ad5` olarak listeleniyor.
- **Bu SHA-1, dosyanın SHA-256 özeti değildir; Qualcomm tarafından yayımlanmış bir bütünlük kanıtı da değildir.** Gerçek dosya indirilmeyip çalıştırılmadığından `clang --version` çıktısı hâlâ doğrulanmış değil.
- Geliştiricisi Qualcomm değil; 10.0.7 adı + notları, OEM'in kullandığı **aynı paket** olduğunu kanıtlamaz.
- Repo boyutu GitHub'ın bildirdiği 261417 KB düzeyinde; içinde Linux ikilileri bulunuyor. Binary provenance ve lisans koşulları ayrıca incelenmeli. Üretim veya gizli runner üzerinde doğrudan çalıştırılmamalı.

## Samsung kaynak yoluyla mevcut CI arasındaki ölçülebilir fark

Claude'un sunucudan **salt-okuma** inceleyip PR #2'de bildirdiği aday stok `Kernel.tar.gz`:
- Boyut **183.277.219 bayt**; SHA-256 `ac29e591a6253dffee61ab1aaacc7abd3f02a027729ed7e8ec2fc753ff57d2d3`.
- Arşivde bulunan `build_kernel.sh` çağrısı `REAL_CC=.../toolchain/llvm-arm-toolchain-ship/10.0/bin/clang` ve `CROSS_COMPILE=.../aarch64-linux-android-4.9/bin/aarch64-linux-android-` kullanıyor; kök Makefile `CC=python scripts/gcc-wrapper.py $(REAL_CC)` yolunu kullanıyor.
- Önceki deneydeki `LLVM=1 CC=clang-14` çağrısı aynı önişleme/derleme komutu değildir.
- Arşivin **tam OEM A235FXXSEEZB1 kaynak sürümü** olduğuna dair Samsung imzası/özet eşleşmesi henüz gösterilmedi. Sunucudaki dosyalar otomatik olarak GitHub/Drive'a aktarılmadı.

## Güvenli, çakışmasız doğrulama sırası

1. **Kaynak kimliği:** Orijinal arşiv için Samsung açık kaynak indirme referansı veya resmî checksum bulunursa eşleştir. Aksi hâlde kaynak 'OEM'e benzeyen fakat doğrulanmamış' etiketiyle kalmalı.
2. **Derleyici kimliği:** Öncelik Qualcomm'un resmî SDLLVM 10.0.7 paketinden yayımlanmış dosya/manifest/hash bulmakta. Üçüncü taraf mirror ikililerine resmî dosyayla byte veya doğrulanabilir paket digest eşitliği olmadan güvenme.
3. **İlk inceleme — çalıştırmadan:** Git commit SHA'ya sabitle; izole, salt-okuma analizinde `sha256sum bin/clang`, `file bin/clang`, `readelf -h bin/clang` ve gerekli dinamik kütüphaneleri kaydet. Git blob SHA ile SHA-256 farklı şeylerdir. Bilinmeyen ikiliye GitHub token, secrets veya özel kaynak erişimi verme.
4. **Derleyici doğrulanırsa:** `clang --version` ve `clang -dM -E -x c /dev/null` çıktısını, gerçek Samsung `gcc-wrapper.py` yoluyla çağrılan `kernel/sched/wait.c` Kbuild komutuyla birlikte kaydet. Repo kaynakları SHA-256 ile sabitlensin.
5. **Önce kendi CRC'si:** Kernelin **kendi** `scripts/genksyms/genksyms` ikilisiyle `__init_waitqueue_head` yerel CRC'sini `Module.symvers` ile birebir üretmeden OEM varsayımı test etme. OEM karşılaştırma tanığı `__init_waitqueue_head=0x92ff04a8` yalnızca **beklenen** referanstır.
6. **Birden fazla şüpheliyi birlikte değiştirme:** Compiler, wrapper, source, Kconfig, CROSS_COMPILE, module sig gibi girdiler tek tek, karşılaştırılabilir matris olarak değerlendirilmeli. OEM Wi-Fi 138 + rdbg 6 CRC farkı sıfırlanmadıkça fail-closed devam eder.

## Claude için koordinasyon

Bu belge Codex tarafındaki `codex/issue-1-a235f-abi-gate` dalındadır. Claude'un `claude/symtypes-analiz` dalındaki `scripts/build_stock_abi.sh`, `scripts/symtypes_intersect.py` ve `.github/workflows/stock-abi-reproduction.yml` dosyalarına dokunulmadı. Claude'un 1.424 `.symtypes` ve genksyms oracle bulguları korunuyor; OEM eşitliği **hâlâ ispatlanmamıştır**.

Referanslar:
- https://github.com/asansoravcilari-pixel/A23_Karnelsu-Edit/pull/2
- https://github.com/sticpaper/Snapdragon-LLVM-ARM-Compiler-10.0.7-for-Android-NDK/blob/a16fec82a8deaf8f742ea54f8de98c021af200d4/RELEASE_NOTES
- https://www.qualcomm.com/developer/software/snapdragon-llvm-compiler
