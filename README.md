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

COPR'dan yayımlanan kurucuyu kurmak için:

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
Main kurucu modeline geçirilmiştir. İlk doğrulanan kurucu yayını
[`1.2.95.453.g0eeebbed-4`](https://github.com/universish/spotify-client..copr..ci/releases/tag/v1.2.95.453.g0eeebbed-4)
olur; COPR'da 17 hedefte başarıyla derlenmiştir. Eski doğrudan istemci RPM/SRPM
ve Actions paket kopyaları kaldırılmış, sürüm etiketleri korunmuştur.
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

----

# Spotify Local RPM Installer — universish

**Please read before downloading and installing:** The GitHub/COPR RPM is a small community-maintained
installer. It does not include the Spotify app, logo, or proprietary binaries.
The Spotify client is downloaded from the official DEB on **your own computer** after your approval,
scanned, and packaged as a local RPM. This is not a project supported
or endorsed by Spotify.

[Legal notice and terms](eula.txt), [disclaimer](DISCLAIMER.txt),
[license scope](LICENSE), and [copyright/attributions](COPYRIGHT) must be read before downloading.
You must comply with Spotify’s [terms applicable to your country](https://www.spotify.com/legal/end-user-agreement/).
Approval does not transfer all legal liability to the user; it does not waive mandatory rights
or eliminate the maintainer’s own obligations. These documents do not grant permission to
RPMs. Do not share the local client RPM.

## Installation and Acceptance

The installer can be downloaded from GitHub Releases and installed using the package manager:

```sh
sudo dnf install ./spotify-*.x86_64.rpm
spotify --setup
```

To install the installer published via COPR:

```sh
sudo dnf copr enable universish/Spotify..Client
sudo dnf install spotify
spotify --setup
```

In a graphical session, a Zenity window opens displaying the legal text and a checkbox.
If you agree, the DEB file is downloaded, verified, and scanned; the local `spotify-client-local`
RPM is built. The package manager then opens with system privileges.
Administrator privileges are used only for the final installation/uninstallation process.

If you decline, the download, build, and execution will stop. If our `spotify-client-local`
package is already installed, system authorization is requested for its removal.
If authorization is not granted or the removal fails, it is not assumed to have been automatically deleted;
this launcher will again refuse to run. Existing LPF/vendor packages are not automatically
removed. You can remove the small installer RPM separately using your package manager.

No graphical confirmation is requested during the DNF/RPM process: the installer can be installed, **but confirmation for the actual Spotify
client comes in the next step**. If the terms of service change, confirmation
will be requested again. The confirmation record is user-specific. A user without a graphical session can
run `spotify --setup --accept-spotify-terms` explicitly after reviewing the text.

```sh
spotify
spotify --debug
spotify --safe-mode
spotify --gpu-mode=native
```

## Local Client Build

1. The size and SHA256 value of the selected official amd64 DEB are verified.
2. ClamAV signatures are updated; if an error occurs, the process stops.
3. The DEB and check files are extracted; Debian installation scripts are not run.
4. The DEB and all extracted contents are scanned using standard malware and heuristic signatures.
5. A separate PUA scan is performed. Only `PUA.*` detections are reported, and the process continues;
   standard malware, scanning errors, encrypted/corrupted content, or exceeding the limit will halt the process.
6. The application tree, such as LPF, is kept intact under `/usr/share/spotify-client/`.
   The RPM `%check` phase re-verifies the SHA256 values of the original files.
7. A local RPM is created, and installation with system privileges is requested.

Reports are located under `${XDG_STATE_HOME:-$HOME/.local/state}/spotify-bootstrap/<version>/`.
Scanning does not guarantee the absence of all unknown threats. Approval, download, and scanning
are performed with user permission; the installer’s RPM scriptlets do not download or run Spotify.

The NVIDIA desktop GL profile tracks active LPF settings; PRIME is applied
on supported hybrid GPUs. NVIDIA variables are not added to AMD/Intel/Nouveau. In the event of an early graphics
error, there is limited ANGLE/software fallback. Ozone/DPI is not forced.
User `spotify-flags.conf` and `spotify.env` files are preserved; the environment file
is not executed as shell code. [GPU details](docs/gpu-launcher.md).

## Automation

The build pipeline now produces only **installer RPMs/SRPMs that do not contain proprietary content**.
It checks for the stable release daily at 12:00 and 17:00 Stockholm time; if no new release
is available, it skips the build. Manual triggering also repackages the same release.
New releases are numbered `-1`, while subsequent releases of the same version are numbered `-2`, `-3`.
The source RPM is scanned; the COPR result is awaited, and then a GitHub release is created.
The Spotify DEB scan is a mandatory step in the user’s local build process.

In the metadata, `download.spotify.com/debian` is used first, followed by `repository.spotify.com`.
The default remains only stable x86_64; there is no ARM/32-bit version.
The difference between LPF source 1.3.4 and the official stable 1.2.95 is explained [in the LPF documentation](docs/lpf-compatibility.md);
testing is not automatically selected.

The `COPR_CONFIG` secret setting and active distribution selection are [in the COPR documentation](docs/copr.md).
It has been ported to the main build model. The first verified build release
is [`1.2.95.453.g0eeebbed-4`](https://github.com/universish/spotify-client..copr..ci/releases/tag/v1.2.95.453.g0eeebbed-4)
; it has been successfully built on 17 targets in COPR. Old direct client RPM/SRPM
and Actions package copies have been removed, while version tags have been preserved.
Nginx, Docker Hub, GHCR, or telemetry are not used. Download charts show GitHub
Releases counters; they do not show the number of active users.

## Development

```sh
python3 -m unittest discover -s tests -v
SPOTIFY_METADATA_DIR=output/metadata python3 src/parser_debian_control_file.py stable spotify-client Version
python3 tools/build_bootstrap.py output/metadata/spotify-client.stable.json output
src/build_binary.sh output/spotify-*.src.rpm output
```

The build source archive is created using an open file list;
producers with unclear licenses from the old fork and Spotify data are not included in this archive.
`src/build_once.sh` preserves the old direct client build solely for local comparisons;
the COPR/GitHub build release does not use this script.


Translated with DeepL.com (free version)


## Kurucu durum ve yeniden deneme / Installer state and retry

```sh
spotify --status
spotify --install
spotify --rebuild
```

`--status` onay, derleme veya kurulum bekleme durumunu gösterir. `--install`,
daha önce hazırlanmış RPM'nin SHA256 ve paket kimliğini yeniden doğrulayarak
kurulumu tekrar dener; yeniden DEB indirmez. `--rebuild` yeni tarama/derleme ister.
Yeni kaynak sürümü veya paketleme revizyonu yeniden onay gerektirir.

`--status` reports approval/build/install readiness. `--install` retries a
previously built RPM after checking its hash and package identity; it does not
repeat the DEB download. `--rebuild` requests a fresh scan/build. New source
versions or bootstrap revisions need renewed approval.

Bu bağımsız kurucu gerçek LPF motorunu kullanmaz. Ayrı pkg-build hesabı ve LPF
bildirim servisi dahil mimari farklar [LPF karşılaştırmasında](docs/lpf-framework-audit.md)
açıklanır. This standalone installer does not use the actual LPF framework;
see the linked comparison for the account/lifecycle/notification differences.
