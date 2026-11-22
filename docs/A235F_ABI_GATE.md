# SM-A235F KernelSU — ABI uygunluk kapıları (A235FXXSEEZB1)

## Hedef

Samsung Galaxy A23 SM-A235F (4G), Android 14, stok Linux
`4.19.157-perf-28692735-abA235FXXSEEZB1`.
SELinux **Enforcing** korunur. KernelSU uygulama bazlı yetkilendirme hedeflenir.
`CONFIG_PANIC_TIMEOUT=0` yalnızca kernel panic sonrası otomatik yeniden başlatmayı
devre dışı bırakır; panic veya donanım watchdog arızasını önlemez.

## Kesin olarak doğrulananlar

- Orijinal boot (96 MiB), SHA-256:
  `2eacbc30868fb7d05657a3504afc2e645da04fe6000d49c56f05bfb00d7e279b`.
- Stok gömülü IKCONFIG (167305 bayt), SHA-256:
  `967db7ebc0389dc053d40e3747056af303959d826fd028a030377e2279e4cfc1`.
  Depo yolu: `configs/a235fxxseezb1_stock.config`.
- Samsung vendor arşivi SHA-256:
  `7ac5fd2c8e002e92965fa5916191135c7ea2ee90f6fab8764e22f9d5abef280a`.
- OEM Wi-Fi `qca_cld3_wlan.ko` ve `rdbg.ko`: stok vermagic uygun.
- Önceki KernelSU derlemesinde Wi-Fi 199 eşleşen / 209 farklı CRC,
  rdbg 14 eşleşen / 20 farklı CRC. **Flash için uygun değil.**
- OEM modüller PKCS#7 + SHA-512 ile imzalıdır. OEM açık sertifikası
  `certs/a235fxxseezb1_oem_trusted.pem` içinde, seri numarası
  `7C2B781205C5CF85AA1BCD9242CD1E4E4FD12AFF`.
  Bu **açık** sertifikadır; özel imza anahtarı değildir.

## Statik test akışı

1. Stok `stock_baseline` profilini *KernelSU olmadan* ve stok IKCONFIG ile derle.
2. `stock_ksu_directhooks` profilini KernelSU + doğrudan hook (KPROBES=n) ile derle.
3. Her profil için `Module.symvers` ve `kernel.config` çıktılarını doğrula.
4. `stock_module_crc.tsv` OEM referansıyla `scripts/compare_oem_crc.py`
   kullanarak modül bazında *sıfır* CRC uyuşmazlığı arayın.
5. Stok profilinde CRC uyumsuzluğu varsa öncelikle kaynak kod farklarını,
   Samsung güvenlik konfigürasyonunu ve orijinal Qualcomm Snapdragon
   LLVM clang 10.0.7 derleyicisini araştırın.
6. Stok profili geçer, KernelSU profili kalırsa hook ve KernelSU değişikliklerini
   ABI açısından değerlendirin; eski CRC değerlerini zorla yazmayın.
7. OEM imzası için `CONFIG_MODULE_SIG_FORCE` ve güvenilir açık
   X.509 sertifikasını ayrıca doğrulayın.

## 23 Kasım 2026: Stok ABI yeniden üretim bulguları

- Stok `boot.img` içindeki derleyici kimliği: **clang 10.0.7 for Android NDK**
  ve GNU ld 2.27.0.20170315. Bu bilgi doğrudan kernel sürüm dizesinden
  okunmuştur; yalnızca `CONFIG_CLANG_VERSION` değerine dayanmaz.
- Google Android'in resmî tarihsel `clang-r370808` paketini Linux runner
  üzerinde çalıştırdık; sonuç **clang 10.0.1**, yani OEM'in tam derleyicisi
  **değil**. Bu paketle derleyip CRC uyumunun garanti olduğunu varsaymayın.
- Tam `clang 10.0.7 for Android NDK` dizgesi Qualcomm'un **Snapdragon LLVM**
  derleyicisine işaret ediyor; Qualcomm'un resmî dağıtım kaynağı
  Qualcomm Software Center'dır. Resmî paket doğrulanmadan rastgele
  üçüncü taraf toolchain binary'sini kernel üretimine eklemeyin.
- 7 numaralı stok referans ve KernelSU direct-hook denemesi nesneleri
  derledi; ancak `aarch64-linux-gnu-ld`, `vmlinux.lds:62` satırında
  `cannot move location counter backwards` hatası verdi.
  Bu, kernel adres/bellek yerleşimi uyuşmazlığıdır; CRC testi henüz geçmedi.
- 8 numaralı denemede linker script, bölüm tablosu, ve oluştuysa
  `Module.symvers` dosyası başarısız build'de de saklanacak şekilde
  tanılama eklendi. Linker script dosyası incelenmeden adresleri,
  `RKP`, `KDP` veya `FIVE` korumalarını rastgele değiştirmeyin.
- Eski başarılı 15 numaralı çekirdeğin OEM modül CRC sonucu
  **Wi-Fi 209, rdbg 20 uyumsuz** kaldığı için bu çekirdek flash edilemez.

## 8–10 numaralı denemeler: Samsung UH/RKP linker çift yerleştirmesi

- Üretilmiş `vmlinux.lds` dosyasında sayfa tabloları
  `idmap_pg_dir` ve `swapper_pg_dir` **iki defa** yer alıyordu:
  `.uh_ro` içinde ve `BSS_SECTION` sonrasında.
- Kök kaynak: `include/asm-generic/vmlinux.lds.h` dosyasındaki
  `CONFIG_RKP` + `CONFIG_UH` korumalı sayfa tablosu ayırımı ile
  `arch/arm64/kernel/vmlinux.lds.S` dosyasındaki koşulsuz ARM64
  ayırımı birlikte etkin.
- `scripts/fix_samsung_uh_linker.py` yalnızca ARM64'ün **tekrarlı**
  BSS-sonrası blokunu `#if !defined(CONFIG_RKP) || !defined(CONFIG_UH)`
  koşuluna alır; Samsung UH/RKP'nin korumalı `.uh_ro` blokunu,
  `FIVE`, `KDP`, `SELinux` ayarlarını değiştirmez.
- Düzeltmenin kaynak metni üzerindeki eşleşmesi doğrulandı. Henüz
  oluşan çekirdeğin link, ABI ve cihaz testlerinin geçeceği doğrulanmadı.
- 8 numaralı stok build bağlantıda başarısız olsa da elde edilmiş
  `Module.symvers` OEM Wi-Fi için **270 eşleşen/138 farklı**,
  `rdbg.ko` için **28 eşleşen/6 farklı** CRC göstermiştir.
  Eski KernelSU build'inde karşılıkları Wi-Fi 199/209, rdbg 14/20 idi.
- Tam kernel bağlanmadığı için bunlar **diagnostik ön sonuçlardır**;
  hiçbir koşulda flash onayı değildir.

## Flash kapısı

Aşağıdakilerin *tamamı* gerçekleşene kadar **Odin/flash YASAK**:

- Wi-Fi/rdbg OEM ABI CRC testi geçer.
- Orijinal Samsung modül imza zincirinin yeni kernelde geçerli olduğu doğrulanır.
- Boot header/DTB/ramdisk koruma, Samsung AVB ve açılış/kurtarma planı doğrulanır.
- Kullanıcı cihaza yönelik flash için açıkça izin verir.

Derleme başarısı ≠ OEM modül uyumu ≠ çalışan KernelSU ≠ güvenli boot.
