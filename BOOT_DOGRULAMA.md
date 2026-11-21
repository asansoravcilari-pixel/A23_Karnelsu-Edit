# SM-A235F KernelSU boot çalışma alanı

## Doğrulanan boot imajı
- Dosya: `boot.img` (kullanıcının sağladığı orijinal imaj)
- Boyut: 100663296 bayt (96 MiB)
- SHA-256: `2eacbc30868fb7d05657a3504afc2e645da04fe6000d49c56f05bfb00d7e279b`
- Dosya türü: Android boot image (Qualcomm / qcom komut satırı)
- `boot.img` ile `boot(1).img` aynı SHA-256 değerine sahip.

## KernelSU derleme durumu
- Önceden sağlanan `A235F_kernel_src_KernelSU.tar.gz` arşivi bütünlük denetimini geçmedi: gzip unexpected end of file / tar unexpected EOF.
- KernelSU entegrasyonu, derleme ve cihazda açılış henüz doğrulanmadı.
- Bu depoda **flash edilmeye hazır bir KernelSU boot imajı yoktur**.

## Güvenli sonraki adımlar
1. Eksiksiz kernel kaynak arşivini ve cihazın yazılım yapı numarasını doğrula.
2. Kaynak entegrasyonunu ve yapılandırmayı incele.
3. Kernel'i derle, derleme loglarını kontrol et ve imajı paketle.
4. İmajı flash etmeden önce cihaz varyantı, firmware ve geri dönüş paketini doğrula.

**Uyarı:** Boot imajını yalnızca isme bakarak başka bir cihaza veya farklı firmware sürümüne flash etmeyin.
