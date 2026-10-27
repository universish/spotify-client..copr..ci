# Spotify RPM — universish

[zicstardust/spotify-rpm-packager](https://github.com/zicstardust/spotify-rpm-packager)
çatalı. Resmî Spotify Debian paketinin yalnızca **kararlı x86_64** sürümünü
`spotify` adlı RPM ve kaynak RPM olarak paketler.

## Kurulum ve hata ayıklama

[GitHub Releases](https://github.com/universish/spotify-client..copr..ci/releases)
sayfasından uygun RPM'i indirdikten sonra:

```sh
sudo dnf install ./spotify-*.x86_64.rpm
spotify
spotify --debug
spotify --debug-log="$HOME/spotify-debug.log"
```

Paket COPR'da başarıyla yayımlandığında:

```sh
sudo dnf copr enable universish/Spotify..Client
sudo dnf install spotify
```

COPR'un barındırma koşulları ve kaynak tanımı [COPR belgesinde](docs/copr.md).
Güncel istemci glibc 2.39 veya üzerini gerektirir; EL8/EL9 gibi eski sistemlerin
bağımlılıkları bu gereksinimi karşılamaz. RPM'in çalışma zamanı bağımlılıkları
korunur. Dağıtım etiketi taşımayan aynı x86_64 RPM, bağımlılıkları karşılayan RPM
dağıtımlarında kullanılabilir; her dağıtımda grafik oturum ve oynatma ayrıca
sınanmalıdır.

## Yerel derleme

Fedora'da gerekli araçlar:

```sh
sudo dnf install bash python3 curl dpkg clamav clamav-freshclam rpm-build binutils tar gzip coreutils desktop-file-utils
src/build_once.sh stable output
src/build_binary.sh output/spotify-*.src.rpm output
sudo dnf install ./output/spotify-*.x86_64.rpm
```

Betikler yönetici olarak çalıştırılmaz. Kaynak paketi hazırlama sırası:

1. Resmî kararlı DEB'i indir; boyutunu ve SHA256 değerini seçilen metaveriyle doğrula.
2. Ayrı ClamAV veritabanını `freshclam` ile güncelle.
3. DEB verilerini ve kontrol dosyalarını aç; Debian kurulum betiklerini çalıştırma.
4. DEB'i ve açılan içeriği özyinelemeli tara; ancak temiz sonuçtan sonra paketle.

Güncelleme hatası, zararlı tespiti, tarama hatası veya tarama sınırının aşılması
paket üretimini durdurur. PUA ve sezgisel tespit ile şifreli/bozuk çalıştırılabilir
uyarıları da derlemeyi durdurur. Tarama bilinen arka kapı ve zararlı imzalarını
kapsar; bilinmeyen her tehdidin yokluğunu kanıtlamaz. Günlükler `output/scan-reports/` altında saklanır.
İsteğe bağlı `BUILTIN_FFMPEG=true` kullanılırsa eklenen kütüphaneler de taranır;
varsayılan değer `false` olur.

`src/build_binary.sh`, Debian/Ubuntu derleyicisinde araçların varlığını doğrudan
doğrular; o sistemin RPM veritabanında kayıtlı olmayan derleme bağımlılıkları
ayrıca sorgulanmaz. RPM'in otomatik ELF çalışma zamanı bağımlılıkları üretilir.

## GitHub Actions ve otomatik COPR gönderimi

Tek yayın akışı [Stable Spotify RPMs and COPR](https://github.com/universish/spotify-client..copr..ci/actions/workflows/spotify-rpm-releases.yml)
olur. Her gün **Europe/Stockholm saat diliminde 12.00 ve 17.00**'de resmî
öncelikle `https://download.spotify.com/debian/dists/stable/non-free/binary-amd64/Packages`
adresini, kullanılamıyorsa
[resmî repository.spotify.com indeksini](https://repository.spotify.com/dists/stable/non-free/binary-amd64/Packages)
kontrol eder. Ana dizinlerin 403 dönmesi tek başına indeks arızası sayılmaz;
seçilen kaynak günlükte belirtilir. GitHub'ın saat dilimi desteği yaz/kış saati geçişini uygular;
yoğunluk nedeniyle gerçek başlatma saati gecikebilir.

- Aynı Spotify sürümü zaten yayımlandıysa indirme, tarama ve derleme işleri atlanır.
- Yeni sürümde kaynak indirilir, SHA256 doğrulanır, ClamAV güncellenir; hem DEB
  hem açılan dosyalar, kurulum betikleri, ELF dosyaları ve iç içe arşivler taranır.
- Temiz sonuçtan sonra RPM ve SRPM oluşturulur; SRPM güncel, uyumlu ve etkin
  COPR hedeflerine otomatik gönderilir. COPR sonucu beklendikten sonra GitHub
  kararlı yayını görünür yapılır. Raporlar workflow artifacts içinde saklanır.
- **Run workflow**, sürüm değişmemiş olsa da her zaman yeni bir paketleme başlatır.

Paket adı `spotify-<SPOTIFY_SÜRÜMÜ>-<PAKETLEME_NO>.x86_64.rpm` biçimindedir.
Yeni Spotify sürümü `-1` ile başlar; aynı sürümün sonraki paketlemeleri `-2`, `-3`
diye devam eder. Mevcut GitHub etiketleri/yayınları ve COPR geçmişi hesaba katılır.
Numara derlemeden önce benzersiz bir Git etiketiyle ayrılır; başarısız denemelerin
ayrılmış numaraları tekrar kullanılmaz. Eski paketler üzerine yazılmaz.

`COPR_CONFIG` repository secret'i zorunludur; yapılandırma ve numaralandırma
ayrıntıları [COPR belgesinde](docs/copr.md) ve [yayın akışında](docs/release-flow.md)
açıklanmıştır. Yeni paketleme için ayrı COPR ekranındaki eski kaynağı yeniden
derlemek yerine **Run workflow** kullanılır. Yerel denemelerde numara açıkça
`SPOTIFY_RELEASE=4 src/build_once.sh stable output` gibi verilebilir; verilmezse
1 kullanılır. Yerel betik GitHub'ın sayacını ayırmaz.

Nginx, Docker Hub, GHCR, konteyner yayınları, Snap ve testing görevleri kaldırılmıştır.
`validate.yml`, betikleri ve regresyon testlerini push/PR olaylarında doğrular.

## GPU, sürücü ve oturum uyarlaması

Başlatıcı her çalıştırmada DRM/sysfs üzerinden GPU'yu ve bağlı sürücüyü,
`XDG_SESSION_TYPE` üzerinden Wayland/X11 oturumunu değerlendirir. NVIDIA PRIME
değişkenleri desteklenen NVIDIA hibrit yapıya uygulanır; Intel/AMD/Nouveau
profiline eklenmez. X11 NVIDIA profili desktop GL, Wayland profili ANGLE/OpenGL
kullanır. Erken ve başarısız GPU başlangıcında sınırlı geri dönüş yapılır.

```sh
spotify --debug
spotify --safe-mode
spotify --gpu-mode=native
```

`--safe-mode` donanım hızlandırmasını kapatıp PRIME seçimlerini temizler.
`--gpu-mode=native` otomatik GPU bayrakları eklemeden kullanıcı ayarlarını kullanır.
Tüm profiller ve RPM yerleştirme örneği [GPU başlatıcı belgesinde](docs/gpu-launcher.md).
Donanım algısı `/usr/bin` dosyasını veya kalıcı kullanıcı yapılandırmasını yeniden
üretmez; bu nedenle oturum/GPU değişiklikleri sonraki başlatmada değerlendirilir.

## Yapılandırma

Dosyalar `${XDG_CONFIG_HOME:-$HOME/.config}/spotify/` altındadır:

- `spotify-flags.conf`: her satırda tek komut satırı argümanı.
- `spotify.env`: her satırda tek `ANAHTAR=değer` ataması; kabuk kodu çalıştırılmaz.

Boş satırlar ve yorumlar yok sayılır; var olan dosyalar korunur.
`SPOTIFY_DEBUG=1 spotify` da terminal hata ayıklamasını açar. Günlük dosyası özel
izinlerle oluşturulur. Yeni yapılandırma Chromium sandbox özelliklerini
varsayılan olarak kapatmaz. Kurulu uygulama dosyalarını yalnızca root değiştirebilir.

## İndirme grafikleri

```sh
python3 tools/download_stats.py --output output/download-stats.html
```

HTML raporu gerçek GitHub Releases RPM indirme sayaçlarını gösterir; yayın
akışından da indirilebilir. Sayaçlar kurulum veya aktif kullanıcı sayısı değildir.
[Spotify Developer panelinin neden bu sayımlara bağlanamadığı](docs/statistics.md)
ve ölçümlerin sınırları ayrıca açıklanmıştır. İstemciden kullanım verisi toplanmaz.
Eski kararlı yayınlar sayaçlarını korumak için otomatik silinmez.

## Doğrulama

```sh
python3 -m unittest discover -s tests -v
```

Testler başlatıcının argüman/çıkış kodu davranışını, özel günlük izinlerini,
metaveri ayrıştırmasını ve ClamAV hata durumlarında paket üretiminin durmasını
kontrol eder. Güncellenen dağıtım/mimari listesinin gerekçeli durumu
[targets.json](packaging/targets.json) içinde saklanır; etkin kapsam yalnızca
kararlı x86_64'tür; COPR'da ek olarak listelenen x86_64_v2 hedefleri
aynı resmî amd64 ikilisini paketleyebilir. 32 bit hedefler için güncel istemci
yayımlanmadığından eski i386 paketi güncel sürüm olarak kullanılmaz. İsteğe bağlı temiz hedef denemesi için
`bash tools/build_target.sh SRPM CHROOT ÇIKTI_KLASÖRÜ` kullanılabilir.

## Lisans

Bu depo paketleme betiklerini içerir. Spotify, Spotify AB'nin özel mülk yazılımıdır.
Kaynak proje: https://github.com/zicstardust/spotify-rpm-packager
