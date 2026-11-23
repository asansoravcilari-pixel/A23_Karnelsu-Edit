# A235FXXSEEZB1 — Kaynak/derleyici köken doğrulaması ve talep yöntemi

> **Araştırma dokümanı.** Burada hiçbir kaynak arşivi OEM ile eşleşmiş sayılmıyor ve hiçbir cihaz/flash doğrulaması iddia edilmiyor. CRC eşleşmesini zorlamak veya güvenlik kontrollerini devre dışı bırakmak hedef değildir.

## Doğruladığımız hedef

- Cihaz: Samsung Galaxy A23 4G, **SM-A235F**.
- Kullanıcının çalıştığı yazılım: **A235FXXSEEZB1**, Android 14, bootloader binary E.
- Samsung [güncelleme geçmişi](https://doc.samsungmobile.com/SM-A235F/023144220519/tur.html): **9 Mart 2026** tarihli sürüm, **5 Şubat 2026** güvenlik yaması.
- Mevcut testlerde Samsung'un OEM Wi-Fi modülü **138** CRC farkı; `rdbg.ko` **6** fark. ABI fail-closed, **flash izni yok**.

## Neden yeni kaynağa ihtiyaç duyulabilir?

Claude'un PR #2 yorumunda raporladığı sunucu arşivi `Kernel.tar.gz` SHA-256 `ac29e591a6253dffee61ab1aaacc7abd3f02a027729ed7e8ec2fc753ff57d2d3` ve 183.277.219 bayttır. Arşivin çoğu üyesinin kayıt tarihi **2024-02-29**, en yenisi **2025-03-06**. Orijinal Samsung `build_kernel.sh` çağrısı, `gcc-wrapper.py` / `REAL_CC` yolunu kullanıyor. Claude'un **clang 11.0.1 + özgün kaynak/çağrı** deneyinde `__init_waitqueue_head` CRC `0x969bb8f4`, eski CI clang14 ile *aynı*, fakat OEM değeri `0x92ff04a8`. Bu, derleyici çağrısı değişikliğinin bu tanık için tek başına çözüm olmadığını gösterir; **kaynağın farklı olabileceği bir hipotezdir**. Arşiv üyelerinin tarihleri tek başına OEM üretim kaynaklarını tanımlamaz; Samsung çıkış/bütünlük kanıtı gereklidir.

## Gerekli kaynak paketi

Samsung Open Source Release Center: https://opensource.samsung.com/

Arama: `SM-A235F`; hedef firmware `A235FXXSEEZB1` ve Android 14. Yayımlanmış kaynak sürümü tam olarak bu derlemeye eşlenmiyorsa, [kaynak talep sayfasından](https://opensource.samsung.com/requestInquiry) ilgili build numarasıyla **eşleşen GNU GPL çekirdek kaynak arşivinin ve oluşturma talimatlarının** talep edilmesi gerekir. Sitenin oturum/doğrulama gereksinimini kullanıcı kendisi tamamlar; otomatik bypass yoktur. Talep veya indirme yapılmadı. Samsung yalnızca kaynak sürümünü genel ürün/Android sürümüyle ilişkilendirebilir; kesin eşleşme olduğu varsayılmaz.

İstek metninde şu tanımlayıcılar yardımcı olur: `SM-A235F`, `A235FXXSEEZB1`, `Android 14`, `Linux 4.19.157-perf`, `CONFIG_MODVERSIONS=y`, Samsung OEM modül ABI eşleşme ihtiyacı. Ayrıca açık kaynak kapsamındaki `build_kernel.sh`, toolchain/Makefile sürümleri ve kaynak paketinin sürüm tanımı sorulabilir. Özel anahtar, imza veya güvenlik devre dışı bırakma talep etmiyoruz.

## Arşiv geldiğinde yapılacak **salt-okuma** ilk kontrol

```bash
python3 scripts/a235f_source_provenance.py Kernel.tar.gz \
  --output source-provenance.json
```

Arşiv için güvenilir bir **bağımsız** SHA-256 bildirildiyse eşleştirme opsiyoneldir:

```bash
python3 scripts/a235f_source_provenance.py Kernel.tar.gz \
  --expected-sha256 'BURAYA_64_HEX_SHA256' \
  --output source-provenance.json
```

*Bu betik* arşivi açmadan yürütme yapmadan okuyarak kendi SHA-256 özetini, dosya tarih histogramını, `build_kernel.sh` varlığını/işaretlerini ve sınırlı kritik dosya içerik özetlerini verir; **Samsung üretim eşitliği kanıtı üretmez**. Rapor asla `flash_approval=true` vermez. Resmî checksum yoksa `hash_matched_supplied_expected=false` kalır. İlk kontrol sonrası tam kaynağın hedef üretim varyantına ait olduğunun ayrıca doğrulanması gerekir.

## Başarı kapısı

Kaynağın sürümü/kimliği doğrulandıktan sonra önce yalnız **stok profil**, aynı OEM yapılandırma, modül ve imzaya uygun derleme girdileriyle CRC karşılaştırılır. CRC eşitliği + OEM modül yüklenebilirliği + AVB/Samsung güven zinciri + gerçek cihaz açılışı birbirinden bağımsız doğrulamalardır. **Tüm kapılar geçilmeden telefon için kernel flash önerilmez.**
