# Spotify yerel RPM kurucusu — universish

**İndirmeden ve kurmadan önce okuyun:** GitHub/COPR RPM'si küçük bir topluluk
kurucusudur. Spotify uygulamasını, logosunu veya özel mülk ikililerini içermez.
Spotify istemcisi, onayınızdan sonra **kendi bilgisayarınızda** resmî DEB'den
indirilir, taranır ve yerel RPM olarak paketlenir. Spotify tarafından desteklenen
veya onaylanan bir proje değildir.

[Hukuki bildirim ve koşullar](eula.txt), [sorumluluk reddi](DISCLAIMER.txt),
[lisans kapsamı](LICENSE) ve [telif/atıflar](COPYRIGHT) indirmeden önce okunmalıdır.
Spotify'ın [ülkenize uygulanan koşullarına](https://www.spotify.com/legal/end-user-agreement/)
uymalısınız. Onay, bütün hukuki sorumluluğu kullanıcıya devretmez; zorunlu hakları
ve bakımcının kendi yükümlülüklerini ortadan kaldırmaz. Bu belgeler Spotify
RPM'lerini yeniden dağıtmak için izin sağlamaz. Yerel istemci RPM'sini paylaşmayın.

## Kurulum ve onay

Kurucu GitHub Releases'dan indirilip paket yöneticisiyle kurulabilir:

```sh
sudo dnf install ./spotify-*.x86_64.rpm
spotify --setup
```

COPR'da yeni kurucu yayımlandığında:

```sh
sudo dnf copr enable universish/Spotify..Client
sudo dnf install spotify
spotify --setup
```

Grafik oturumda hukuki metni ve onay kutusunu gösteren Zenity penceresi açılır.
Onay verirseniz DEB indirilir, doğrulanır ve taranır; yerel `spotify-client-local`
RPM'si üretilir. Ardından sistem yetkilendirmesiyle paket yöneticisi açılır.
Yönetici yetkisi yalnızca son kurulum/kaldırma işlemi için kullanılır.

Reddederseniz indirme, derleme ve çalıştırma durur. Bizim `spotify-client-local`
paketimiz zaten kuruluysa kaldırılması için sistem yetkilendirmesi istenir.
Yetki verilmezse veya kaldırma başarısızsa otomatik silindiği iddia edilmez;
bu başlatıcı yine çalıştırmayı reddeder. Mevcut LPF/vendor paketleri otomatik
kaldırılmaz. Küçük kurucu RPM'yi paket yöneticinizle ayrıca kaldırabilirsiniz.

DNF/RPM işlemi sırasında grafik onay istenmez: kurucu kurulabilir, **asıl Spotify
istemcisi için onay sonraki adımdadır**. Koşul bildirimi değişirse yeniden onay
istenir. Onay kaydı kullanıcıya özeldir. Grafik oturumu olmayan kullanıcı metni
inceledikten sonra açıkça `spotify --setup --accept-spotify-terms` çalıştırabilir.

```sh
spotify
spotify --debug
spotify --safe-mode
spotify --gpu-mode=native
```

## Yerel istemci üretimi

1. Seçilen resmî amd64 DEB'in boyutu ve SHA256 değeri doğrulanır.
2. ClamAV imzaları güncellenir; hata olursa işlem durur.
3. DEB ve kontrol dosyaları açılır; Debian kurulum betikleri çalıştırılmaz.
4. DEB ve bütün açılmış içerik normal zararlı/sezgisel imzalarla taranır.
5. Ayrı PUA taraması yapılır. Yalnız `PUA.*` tespitleri raporlanıp devam edilir;
   normal zararlı, tarama hatası, şifreli/bozuk içerik veya limit aşımı durdurur.
6. LPF gibi uygulama ağacı `/usr/share/spotify-client/` altında eksiksiz tutulur.
   RPM `%check` aşaması özgün dosyaların SHA256 değerlerini yeniden doğrular.
7. Yerel RPM oluşturulur ve sistem yetkilendirmesiyle kurulması istenir.

Raporlar `${XDG_STATE_HOME:-$HOME/.local/state}/spotify-bootstrap/<sürüm>/` altındadır.
Tarama bilinmeyen bütün tehditlerin yokluğunu kanıtlamaz. Onay, indirme ve tarama
kullanıcı yetkisiyle yapılır; kurucu RPM scriptlet'leri Spotify indirmez/çalıştırmaz.

NVIDIA desktop GL profili çalışan LPF ayarlarını izler; desteklenen hibrit GPU'da
PRIME uygulanır. AMD/Intel/Nouveau'ya NVIDIA değişkenleri eklenmez. Erken grafik
hatasında sınırlı ANGLE/yazılım geri dönüşü vardır. Ozone/DPI zorlanmaz.
Kullanıcı `spotify-flags.conf` ve `spotify.env` dosyaları korunur; ortam dosyası
kabuk kodu olarak çalıştırılmaz. [GPU ayrıntıları](docs/gpu-launcher.md).

## Otomasyon

Yayın akışı artık yalnızca **özel mülk içerik taşımayan kurucu RPM/SRPM** üretir.
Stockholm saatiyle her gün 12.00 ve 17.00'de stable sürümü denetler; yeni sürüm
yoksa derlemeden çıkar. Elle tetikleme aynı sürümü de yeniden paketler.
Yeni sürüm `-1`, aynı sürümün tekrarları `-2`, `-3` olarak numaralanır.
Kurucu kaynak RPM'si taranır; COPR sonucu beklenir ve ardından GitHub yayını açılır.
Spotify DEB taraması kullanıcıdaki yerel üretimin zorunlu kapısıdır.

Metaveride önce download.spotify.com/debian, sonra repository.spotify.com
kullanılır. Varsayılan hâlâ yalnız stable x86_64'tür; ARM/32 bit yoktur.
LPF'nin 1.3.4 kaynağı ile resmî stable 1.2.95 farkı [LPF belgesinde](docs/lpf-compatibility.md)
açıklanır; testing otomatik seçilmez.

`COPR_CONFIG` secret ayarı ve etkin dağıtım seçimi [COPR belgesindedir](docs/copr.md).
Yeni kurucu henüz main'e birleştirilmediyse eski main iş akışı eski davranışı
korur; bu dalın varlığı eski yayınları otomatik silmez.
Nginx, Docker Hub, GHCR veya telemetri kullanılmaz. İndirme grafikleri GitHub
Releases sayaçlarını gösterir, aktif kullanıcı sayısını göstermez.

## Geliştirme

```sh
python3 -m unittest discover -s tests -v
SPOTIFY_METADATA_DIR=output/metadata python3 src/parser_debian_control_file.py stable spotify-client Version
python3 tools/build_bootstrap.py output/metadata/spotify-client.stable.json output
src/build_binary.sh output/spotify-*.src.rpm output
```

Kurucu kaynak arşivi açık dosya listesiyle oluşturulur; eski çatala ait
lisansı belirsiz üreticiler ve Spotify verileri bu arşive alınmaz.
`src/build_once.sh` eski doğrudan istemci üretimini yalnız yerel karşılaştırmalar
 için korur; COPR/GitHub kurucu yayını bu betiği kullanmaz.
