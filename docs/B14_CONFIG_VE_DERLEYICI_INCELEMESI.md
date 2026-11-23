# SM-A235F B14: stok yapılandırma ve derleyici incelemesi

## Kanıt ve yöntem

- Gömülü OEM IKCONFIG: `configs/a235fxxseezb1_stock.config`, SHA-256
  `967db7ebc0389dc053d40e3747056af303959d826fd028a030377e2279e4cfc1`.
- GitHub Actions stok profil derlemesi [run 10](https://github.com/asansoravcilari-pixel/A23_Karnelsu-Edit/actions/runs/45080985922)
  (`stock_baseline`) çıktısındaki `result/kernel.config`, SHA-256
  `bc5ed05ef008e408bcbfbb496f55fd5d3e98d5206af9fb3e9a1e951f311bd1ae`.
- Aynı artifact içindeki `result/config-diff.txt` ile iki yapılandırma
  karşılaştırıldı. Tam anahtar düzeyinde **12 fark** var. `Module.symvers`
  karşılaştırması ayrıca 138 Wi-Fi ve 6 rdbg CRC farkıyla başarısız oldu.

| Anahtar | Stok | Run 10 | Değerlendirme |
| --- | --- | --- | --- |
| `CONFIG_CLANG_VERSION` | `100007` | `140006` | Derleyici kimliği farklı; tek başına CRC kök nedeni kanıtı değil. |
| `CONFIG_PROCA_CERTIFICATES_XATTR` | `y` | yok | Kaynak/Kconfig ve bu seçeneğin tip tanımlarına etkisi araştırılmalı. |
| `CONFIG_PROCA_CERT_ENG`, `CONFIG_PROCA_CERT_USER` | sertifika adları | yok | PROCA bağımlılığı incelenmeli. |
| `CONFIG_PROCA_CERTIFICATES_DB` | `n` | yok | Kaynakta yokluğu/bağımlılığı incelenmeli. |
| `CONFIG_SYSTEM_TRUSTED_KEYS` | boş | OEM açık sertifikası | İmza güveni ayrı doğrulama gerektirir. |
| `CONFIG_KSU`, `CONFIG_QCA_CLD_WLAN` | yok | `n` | Run 10 stok profili; etkinleştirilmiş bir özellik görünmüyor. |
| `CONFIG_DISABLE_LOCKSCREEN_USB_RESTRICTION`, `CONFIG_MACH_A23_KOR_SINGLE`, `CONFIG_MACH_A23_LTN_OPEN`, `CONFIG_SBP_FG` | `n` | yok | Kconfig farkı; CRC etkisi gösterilmedi. |

Kontrol edilen yapılandırmalar iki tarafta da aynı: `CONFIG_PREEMPT=y`,
`CONFIG_PREEMPT_COUNT=y`, `CONFIG_PREEMPT_RCU=y`, `CONFIG_LOCKDEP_SUPPORT=y`,
`CONFIG_RKP=y`, `CONFIG_UH=y`, `CONFIG_KDP=y`, `CONFIG_MODVERSIONS=y`;
`CONFIG_DEBUG_SPINLOCK` ve `CONFIG_PROVE_LOCKING` kapalı. Bu karşılaştırma
başka kaynak/başlık farklarını dışlamaz.

## Derleyici kimliği ve sonraki ayrım

OEM boot sürüm metnindeki `clang 10.0.7 for Android NDK`, run 10'un
`CONFIG_CLANG_VERSION=140006` değeriyle aynı derleyici değildir. Qualcomm'un
[resmî Snapdragon LLVM sayfası](https://www.qualcomm.com/developer/software/snapdragon-llvm-compiler)
Android NDK sürümünün oturum açarak indirildiğini belirtiyor. Bu incelemede
10.0.7 sürümünün resmî paket kimliği veya SHA-256 özeti doğrulanamadı;
üçüncü taraf ikili dosya build girdisi olarak kabul edilmedi.

Linux çekirdeği [modül sürümleme belgesine](https://docs.kernel.org/kbuild/gendwarfksyms.html)
göre CRC, `genksyms` tarafından önişlenmiş sembol tipi üzerinden üretildiğinden,
derleyicinin kod üretim sürümü tek başına 144 farklı CRC'yi açıklamaz.
Derleyici/önişleyici makroları, kaynak başlıkları ve ilgili `CONFIG_` değerleri
sembol tiplerini değiştirebilir. Sonraki kanıt: aynı build girdilerinden
`.symtypes` çıktısı alıp örneğin `__wake_up` ve `__init_waitqueue_head`
tiplerini diğer eşleşen sembollerle karşılaştırmak; ardından yalnızca
kanıtlanan kaynak veya yapılandırma farkını düzeltip stok ve KernelSU
profillerini yeniden ölçmek.

Bu belge derleme, ABI eşitliği, Samsung imza zinciri veya cihaz açılışı
onayı vermez. Burada yeni kernel imajı üretilmedi ve flash yapılmadı.

## 23 Kasım 2026: iki profilde sembol tipi kanıtı

Claude'un `claude/symtypes-analiz` dalındaki
[run 45111234778](https://github.com/asansoravcilari-pixel/A23_Karnelsu-Edit/actions/runs/45111234778)
başarılı stok ve KernelSU derlemelerinin `result/symtypes.tar.zst`
artifact'ları karşılaştırıldı. `kernel/sched/wait.symtypes`,
`kernel/sched/completion.symtypes`, `net/core/skbuff.symtypes` ve
`drivers/base/core.symtypes` dosyalarında ortak anahtarların sırasıyla
879, 868, 1018 ve 807 tanımında **sıfır farklı gövde** bulundu.
`wait_queue_head`, `completion`, `spinlock_t` ve `raw_spinlock` iki profil
arasında aynı. Bu, OEM'in tipleriyle eşitlik kanıtı değildir; stok OEM
`.symtypes` çıktısı mevcut değildir.

Stok profilinin 1424 `.symtypes` dosyasında aynı anahtar için 324 farklı
gövde tespit edildi; çoğu bir dosyadaki `{ UNKNOWN }` ileri bildirim ile
başka dosyadaki tam yapı tanımıdır. Bu yüzden farklı çeviri birimlerinin
tanımlarını rastgele birleştirip tip grafiği üzerinden tek neden seçmek
yanıltıcı olabilir. Samsung `qspinlock` içindeki `task_struct *owner`
üyesi grafiği ağ ve soket tiplerine kadar genişletir. Tip grafiği yalnızca
aday üretir; OEM'e özgü ön işleme, kaynak başlığı veya doğrulanmış OEM
derleyicisiyle karşılaştırmalı CRC ölçümü hâlâ gereklidir.

## Kaynak başlığı dar tanısı

[Run 45114881716](https://github.com/asansoravcilari-pixel/A23_Karnelsu-Edit/actions/runs/45114881716)
Samsung kaynak arşivini sabit SHA-256 özetiyle doğrulayıp yalnızca beş
başlığı `a23-oem-type-headers` artifact'ına çıkardı: `wait.h`,
`completion.h`, `spinlock_types.h`, ARM64 `spinlock_types.h` ve
`qspinlock_types.h`. Kaynakta `wait_queue_head` iki üyesi, `completion`
iki üyesi ile koşulsuz tanımlanıyor ve ilgili `.symtypes` gövdeleriyle
eşleşiyor. `raw_spinlock` ek alanları `CONFIG_DEBUG_SPINLOCK` veya
`CONFIG_DEBUG_LOCK_ALLOC`; `qspinlock` ek `owner_cpu`/`owner` alanları
`CONFIG_DEBUG_QSPINLOCK_OWNER` koşuluna bağlı. OEM IKCONFIG ve yeniden
derlenen yapılandırmada `CONFIG_DEBUG_QSPINLOCK_OWNER=y`,
`CONFIG_SMP=y`, `CONFIG_NR_CPUS=8` aynı. Bu, yalnızca bu kaynak ve
config çiftini doğrular; OEM'in üretimde kullandığı kaynak dosyalarının
birebir aynı olduğuna ilişkin kanıt yoktur. Özellikle OEM CRC farkını
başlıklardaki koşulları rastgele kapatarak çözmüş saymayın.

## PROCA yapılandırması kaynak taraması

[Run 45115180656](https://github.com/asansoravcilari-pixel/A23_Karnelsu-Edit/actions/runs/45115180656)
aynı sabit kaynak arşivindeki 2 MiB altı bütün `.c`, `.h` ve
`Kconfig*` dosyalarını `PROCA_CERTIFICATES_XATTR`, `PROCA_CERT_ENG` ve
`PROCA_CERT_USER` dizgeleri için taradı; **sıfır eşleşme** buldu
(`proca-config-references.txt`). OEM IKCONFIG'te bulunan seçeneklerin
yeniden derleme `olddefconfig` aşamasında kaybolması bu kaynak arşivinde
ilgili tanımların yokluğuyla tutarlıdır. Kaynak ağacı OEM üretim
girdisiyle birebir eşdeğer sayılamaz. Bu bulgu, PROCA'nın tek başına
144 sembol CRC farkına yol açtığını kanıtlamaz; eksik OEM kodunun
sembol tiplerine etkisi ayrıca karşılaştırılmalıdır.
