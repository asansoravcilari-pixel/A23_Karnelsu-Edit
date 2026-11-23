# Codex raporu — SM-A235F B14 OEM ABI (23 Kasım 2026)

## Yapılan düzeltme

- Gerçek, metin tabanlı A235FXXSEEZB1 OEM modül CRC referansı depoya eklendi. `compare_oem_crc.py` hem modül başına beklenen benzersiz içe aktarım sayılarını (408/34) hem referansın SHA-256 özetini doğruluyor. Sayıları koruyarak sembol ya da CRC değiştirmek artık geçerli bir referans sayılmıyor.
- Testler bu gerçek referanstan veri üretiyor; boş/eksik, bozuk, yinelenmiş, beklenmeyen ve aynı sayıda değiştirilmiş girdiler sınanıyor. PR açıldığında da regresyon iş akışı çalışacak.
- Tam 144 farkın metin raporu `docs/SM-A235F-B14-run10-CRC-report.txt` içinde saklandı. Kernel imajı veya OEM `.ko` ikilileri PR'ye eklenmedi.

## Gerçek çalıştırma ve kanıt

- `python3 -m unittest discover -s tests -p 'test_compare_oem_crc.py' -v`: **15 test geçti** (`Ran 15 tests`, `OK`).
- GitHub Actions stok derleme 10 (`45080985922`, başarılı), `Module.symvers` ile OEM referansı: `qca_cld3_wlan.ko match=270 mismatch=138 missing=0`; `rdbg.ko match=28 mismatch=6 missing=0`. Karşılaştırıcı **exit 1**, `RESULT: FAIL CLOSED — DO NOT FLASH` verdi.
- GitHub Actions derleme 8 (`45079646691`, linker hatası) stok ve KernelSU doğrudan hook profillerinin her biri: aynı **138+6** fark; iki tam fark listesi eşit. 10 numaralı başarılı stok build'in 144 fark listesi de 8 numaralı listeyle eşit. Başarılı derleme OEM ABI uyumu anlamına gelmiyor.

## Engel ve sonraki teknik adım

144 farkın kesin kaynağı bu verilerle kanıtlanamıyor. OEM boot sürüm metninde `clang 10.0.7 for Android NDK` geçiyor; mevcut build `clang-14` kullanıyor, denenmiş resmî Android `clang-r370808` paketi 10.0.1. Eksik olan, OEM'in tam Snapdragon LLVM 10.0.7 derleyicisinin doğrulanabilir dağıtımı (kimlik ve SHA-256) ile OEM modül/çekirdek üretiminde kullanılan tam derleyici bayrakları ve kaynak revizyonunun kanıtıdır. Bu girdiler edinilince aynı stok yapılandırmasında iki profili yeniden derleyip CRC listesini karşılaştırmak gerekir; CRC değerlerini zorla değiştirmek çözüm değildir.

OEM modül imzalarının yeni kernelde Samsung güven zincirince kabulü, AVB/SignerVer02 ve Samsung RKP/UH/KDP davranışı ve gerçek cihazın açılması doğrulanmadı. Bu PR herhangi bir flash edilebilir veya güvenli boot imajı üretmez ya da önermiyor. APatch stok boot için yapısal yama sonucu cihaz testi sayılmaz.
