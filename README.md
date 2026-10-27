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
sudo dnf install bash python3 curl dpkg clamav clamav-freshclam rpm-build binutils tar gzip coreutils
src/build_once.sh stable output
src/build_binary.sh output/spotify-*.src.rpm output
sudo dnf install ./output/spotify-*.x86_64.rpm
```

Betikler yönetici olarak çalıştırılmaz. Kaynak paketi hazırlama sırası:

1. Resmî kararlı DEB'i indir; boyutunu ve SHA256 değerini seçilen metaveriyle doğrula.
2. Ayrı ClamAV veritabanını `freshclam` ile güncelle.
3. DEB verilerini ve kontrol dosyalarını aç; Debian kurulum betiklerini çalıştırma.
4. Açılan içeriği özyinelemeli tara; ancak temiz sonuçtan sonra paketle.

Güncelleme hatası, zararlı tespiti, tarama hatası veya tarama sınırının aşılması
paket üretimini durdurur. Günlükler `output/scan-reports/` altında saklanır.
İsteğe bağlı `BUILTIN_FFMPEG=true` kullanılırsa eklenen kütüphaneler de taranır;
varsayılan değer `false` olur.

`src/build_binary.sh`, Debian/Ubuntu derleyicisinde araçların varlığını doğrudan
doğrular; o sistemin RPM veritabanında kayıtlı olmayan derleme bağımlılıkları
ayrıca sorgulanmaz. RPM'in otomatik ELF çalışma zamanı bağımlılıkları üretilir.

## GitHub Actions

`spotify-rpm-releases.yml` günlük ve elle tetiklenen tek yayın akışıdır. Yalnızca
kararlı x86_64 RPM ve SRPM üretir; tarama/derleme kanıtlarını saklar. Sürüm
metaverisi işler arasında sabitlenir. Dosyalar hazır olmadan yeni yayın görünür
hale getirilmez. `force_release`, aynı sürümün dosyalarını yeniden üretir.

Nginx, Docker Hub, GHCR, konteyner yayınları, Snap ve testing sürüm görevleri
kaldırılmıştır. `validate.yml` betiklerin sözdizimini ve regresyon testlerini
kontrol eder. `copr.yml` isteğe bağlı, elle tetiklenen COPR kaynak derlemesidir.

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
