# Sonicradle — yerel RPM kurucusu — universish

> Bu belge Sonicradle geçişindeki kaynak kod davranışını anlatır. Eski `spotify`
> RPM'si yeni komutları içermez; gerçek COPR yayın sonucu ayrıca doğrulanmalıdır.

**İndirmeden ve kurmadan önce okuyun:** COPR RPM'si küçük bir topluluk
kurucusudur. Spotify uygulamasını, logosunu veya özel mülk ikililerini içermez.
Spotify istemcisi, onayınızdan sonra **kendi bilgisayarınızda** resmî DEB'den
indirilir, CI tarama kaydındaki SHA256 ile doğrulanır ve yerel RPM olarak paketlenir. Spotify tarafından desteklenen
veya onaylanan bir proje değildir.

[Güncel hukuki bildirim ve koşullar](bootstrap/NOTICE.txt), [sorumluluk reddi](bootstrap/DISCLAIMER.txt),
[lisans kapsamı](LICENSE) ve [telif/atıflar](COPYRIGHT) indirmeden önce okunmalıdır.
Spotify'ın [ülkenize uygulanan koşullarına](https://www.spotify.com/legal/end-user-agreement/)
uymalısınız. Onay, bütün hukuki sorumluluğu kullanıcıya devretmez; zorunlu hakları
ve bakımcının kendi yükümlülüklerini ortadan kaldırmaz. Bu belgeler Spotify
RPM'lerini yeniden dağıtmak için izin sağlamaz. Yerel istemci RPM'sini paylaşmayın.

## Kurulum ve onay

Kurucu RPM yalnız COPR üzerinden dağıtılır; GitHub Releases RPM yayını kullanılmaz.

COPR'dan yayımlanan kurucuyu kurmak için:

```sh
sudo dnf copr enable universish/Spotify..Client
sudo dnf install sonicradle
sonicradle --setup
```

Grafik oturumda hukuki metni ve onay kutusunu gösteren Zenity penceresi açılır.
Onay verirseniz DEB indirilir ve CI tarama kaydındaki SHA256 ile doğrulanır; yerel `sonicradle-client-local`
RPM'si üretilir. Ardından sistem yetkilendirmesiyle paket yöneticisi açılır.
Yönetici yetkisi yalnızca son kurulum/kaldırma işlemi için kullanılır.

Reddederseniz indirme, derleme ve çalıştırma durur. Bizim `sonicradle-client-local`
paketimiz zaten kuruluysa kaldırılması için sistem yetkilendirmesi istenir.
Yetki verilmezse veya kaldırma başarısızsa otomatik silindiği iddia edilmez;
bu başlatıcı yine çalıştırmayı reddeder. Mevcut LPF/vendor paketleri otomatik
kaldırılmaz. Küçük kurucu RPM'yi paket yöneticinizle ayrıca kaldırabilirsiniz.

DNF/RPM işlemi sırasında grafik onay istenmez: kurucu kurulabilir, **asıl Spotify
istemcisi için onay sonraki adımdadır**. Koşul bildirimi değişirse yeniden onay
istenir. Onay kaydı kullanıcıya özeldir. Grafik oturumu olmayan kullanıcı metni
inceledikten sonra açıkça `sonicradle --setup --accept-spotify-terms` çalıştırabilir.

```sh
sonicradle
sonicradle --debug
sonicradle --safe-mode
sonicradle --gpu-mode=native
```

## Yerel istemci üretimi

1. GitHub Actions sanal makinesinde resmî amd64 DEB doğrulanır ve ClamAV imzaları güncellenir.
2. DEB ve açılmış içerik taranır; hata veya normal zararlı tespiti COPR gönderimini durdurur.
3. Ayrı PUA taramasında yalnız `PUA.*` tespitleri raporlanıp devam edilir.
4. Kurucuya kaynak SHA256 değerine bağlı tarama kaydı eklenir; DEB kurucuya eklenmez.
5. Kullanıcı bilgisayarında aynı DEB indirilip boyutu/SHA256 değeri doğrulanır;
   ClamAV kurulmaz veya çalıştırılmaz. Debian kurulum betikleri çalıştırılmadan açılır.
6. LPF gibi uygulama ağacı `/usr/share/sonicradle-client/` altında eksiksiz tutulur.
   RPM `%check` aşaması özgün dosyaların SHA256 değerlerini yeniden doğrular.
7. Yerel RPM oluşturulur ve sistem yetkilendirmesiyle kurulması istenir.

Yerel doğrulama/derleme kayıtları `${XDG_STATE_HOME:-$HOME/.local/state}/sonicradle-bootstrap/<sürüm>/`
altındadır; ClamAV raporları Actions üzerinde tutulur.
Tarama bilinmeyen bütün tehditlerin yokluğunu kanıtlamaz. Onay, yerel indirme ve paketleme
kullanıcı yetkisiyle yapılır; kurucu RPM scriptlet'leri Spotify indirmez/çalıştırmaz.

NVIDIA desktop GL profili çalışan LPF ayarlarını izler; desteklenen hibrit GPU'da
PRIME uygulanır. AMD/Intel/Nouveau'ya NVIDIA değişkenleri eklenmez. Erken grafik
hatasında sınırlı ANGLE/yazılım geri dönüşü vardır. Ozone/DPI zorlanmaz.
Kullanıcı `sonicradle/flags.conf` ve `sonicradle/environment.conf` dosyaları korunur; ortam dosyası
kabuk kodu olarak çalıştırılmaz. [GPU ayrıntıları](docs/gpu-launcher.md).

## Otomasyon

Yayın akışı artık yalnızca **özel mülk içerik taşımayan kurucu RPM/SRPM** üretir.
Stockholm saatiyle her gün 12.00 ve 17.00'de iki kanalın sürümünü denetler; yeni sürüm
yoksa derlemeden çıkar. Elle tetikleme aynı sürümü de yeniden paketler.
Yeni sürüm `-1`, aynı sürümün tekrarları `-2`, `-3` olarak numaralanır.
Resmî stable/testing DEB'ler ve açılmış içerikleri Actions üzerinde taranır;
COPR sonucu beklenir. GitHub Releases oluşturulmaz. Geçici DEB/RPM dosyaları temizlenir;
barındırılan sanal makinenin kapatılmasını GitHub yönetir.

Metaveride önce download.spotify.com/debian, sonra repository.spotify.com
kullanılır. Varsayılan stable x86_64'tür; `-unstable` yalnız açıkça istendiğinde testing seçer. ARM/32 bit yoktur.
LPF'nin 1.3.4 kaynağı ile resmî stable 1.2.95 farkı [LPF belgesinde](docs/lpf-compatibility.md)
açıklanır; testing otomatik seçilmez. RPM Fusion Fedora 44/Rawhide kayıtları en son
kontrol edilir; resmî DEB kanalı ve SHA256 değerini geçersiz kılamaz.

`COPR_CONFIG` secret ayarı ve etkin dağıtım seçimi [COPR belgesindedir](docs/copr.md).
Main kurucu modeline geçirilmiştir. Önceki doğrulanan `1.2.95.453.g0eeebbed-4`
yayını tarihsel kayıttır; yeni politika GitHub RPM yayını yapmaz. Temizlik ve COPR
sonuçları [doğrulama kaydında](docs/validation.md) ayrıca belgelenir. Nginx, Docker Hub,
GHCR veya telemetri kullanılmaz. GitHub dosyaları silinince indirme sayaçları kaybolur;
COPR indirme sayısı da aktif kullanıcı sayısı değildir.

## Geliştirme

```sh
python3 -m unittest discover -s tests -v
```

Paket üretimi iki kanalın metaverisini ve geçerli Actions tarama kaydını gerektirir;
komutların sırası [yayın akışında](docs/release-flow.md) ve workflow dosyasındadır.
Kurucu kaynak arşivi açık dosya listesiyle oluşturulur; eski çatala ait
lisansı belirsiz üreticiler ve Spotify verileri bu arşive alınmaz.
`src/build_once.sh` eski doğrudan istemci üretimini yalnız yerel karşılaştırmalar
için korur; COPR/GitHub kurucu yayını bu betiği kullanmaz.

----

# Sonicradle Local RPM Installer — universish

> This guide describes the Sonicradle source transition. The older `spotify`
> RPM does not contain these commands; the new COPR publication must be verified separately.

**Please read before downloading and installing:** The COPR RPM is a small community-maintained
installer. It does not include the Spotify app, logo, or proprietary binaries.
The Spotify client is downloaded from the official DEB on **your own computer** after your approval,
verified against the CI-scanned source hash, and packaged as a local RPM. This is not a project supported
or endorsed by Spotify.

[Current legal notice and terms](bootstrap/NOTICE.txt), [disclaimer](bootstrap/DISCLAIMER.txt),
[license scope](LICENSE), and [copyright/attributions](COPYRIGHT) must be read before downloading.
You must comply with Spotify’s [terms applicable to your country](https://www.spotify.com/legal/end-user-agreement/).
Approval does not transfer all legal liability to the user; it does not waive mandatory rights
or eliminate the maintainer’s own obligations. These documents do not grant permission to
redistribute Spotify RPMs. Do not share the local client RPM.

## Installation and Acceptance

The installer RPM is distributed through COPR; GitHub Releases is not an RPM publication channel.

To install the installer published via COPR:

```sh
sudo dnf copr enable universish/Spotify..Client
sudo dnf install sonicradle
sonicradle --setup
```

In a graphical session, a Zenity window opens displaying the legal text and a checkbox.
If you agree, the DEB file is downloaded and verified against the CI-scanned source hash; the local `sonicradle-client-local`
RPM is built. The package manager then opens with system privileges.
Administrator privileges are used only for the final installation/uninstallation process.

If you decline, the download, build, and execution will stop. If our `sonicradle-client-local`
package is already installed, system authorization is requested for its removal.
If authorization is not granted or the removal fails, it is not assumed to have been automatically deleted;
this launcher will again refuse to run. Existing LPF/vendor packages are not automatically
removed. You can remove the small installer RPM separately using your package manager.

No graphical confirmation is requested during the DNF/RPM process: the installer can be installed, **but confirmation for the actual Spotify
client comes in the next step**. If the terms of service change, confirmation
will be requested again. The confirmation record is user-specific. A user without a graphical session can
run `sonicradle --setup --accept-spotify-terms` explicitly after reviewing the text.

```sh
sonicradle
sonicradle --debug
sonicradle --safe-mode
sonicradle --gpu-mode=native
```

## Local Client Build

1. GitHub Actions verifies the official amd64 DEB and updates ClamAV signatures.
2. The DEB and extracted content are scanned; malware, errors and exceeded limits stop COPR delivery.
3. A separate PUA pass reports PUA-only matches without treating them as confirmed malware.
4. The payload-free bootstrap records the source SHA256 and CI scan result, not the application.
5. On your computer, the same DEB is downloaded, its size/hash checked and its contents extracted
   without running Debian scripts. ClamAV is neither installed nor run on your computer.
6. The application tree, such as LPF, is kept intact under `/usr/share/sonicradle-client/`.
   The RPM `%check` phase re-verifies the SHA256 values of the original files.
7. A local RPM is created, and installation with system privileges is requested.

Local verification/build records are under `${XDG_STATE_HOME:-$HOME/.local/state}/sonicradle-bootstrap/<version>/`.
ClamAV scan reports are retained in Actions instead.
Scanning does not guarantee the absence of all unknown threats. Approval, local download and packaging
are performed as the requesting user; the installer’s RPM scriptlets do not download or run Spotify.

The NVIDIA desktop GL profile tracks active LPF settings; PRIME is applied
on supported hybrid GPUs. NVIDIA variables are not added to AMD/Intel/Nouveau. In the event of an early graphics
error, there is limited ANGLE/software fallback. Ozone/DPI is not forced.
User `sonicradle/flags.conf` and `sonicradle/environment.conf` files are preserved; the environment file
is not executed as shell code. [GPU details](docs/gpu-launcher.md).

## Automation

The build pipeline now produces only **installer RPMs/SRPMs that do not contain proprietary content**.
It checks for the stable release daily at 12:00 and 17:00 Stockholm time; if no new release
is available, it skips the build. Manual triggering also repackages the same release.
New releases are numbered `-1`, while subsequent releases of the same version are numbered `-2`, `-3`.
The official stable/testing DEBs and their extracted contents are scanned in Actions;
COPR completion is awaited. No GitHub Release is created. Temporary DEB/RPM files
are removed; GitHub manages teardown of the hosted VM.

In the metadata, `download.spotify.com/debian` is used first, followed by `repository.spotify.com`.
The default is stable x86_64; explicit `-unstable` selects testing. There is no ARM/32-bit version.
The difference between LPF source 1.3.4 and the official stable 1.2.95 is explained [in the LPF documentation](docs/lpf-compatibility.md);
testing is not automatically selected. RPM Fusion Fedora 44/Rawhide references
are checked last and cannot override the official DEB channel/hash.

The `COPR_CONFIG` secret setting and active distribution selection are [in the COPR documentation](docs/copr.md).
Main uses the payload-free bootstrap model. The previously verified
`1.2.95.453.g0eeebbed-4` publication is historical; the new policy does not publish
RPMs in GitHub Releases. Cleanup and COPR results are recorded separately in the
[validation log](docs/validation.md). Nginx, Docker Hub, GHCR and telemetry are not used.
Deleting GitHub assets removes their download counters; COPR downloads also do
not measure active users.

## Development

```sh
python3 -m unittest discover -s tests -v
```

Package construction requires both channel records and valid Actions scan evidence;
the sequence is documented in [the release flow](docs/release-flow.md) and workflow.
The build source archive is created using an explicit allowlist;
producers with unclear licenses from the old fork and Spotify data are not included in this archive.
`src/build_once.sh` preserves the old direct client build solely for local comparisons;
the COPR/GitHub build release does not use this script.


Translated with DeepL.com (free version)


## Kurucu durum ve yeniden deneme / Installer state and retry

```sh
sonicradle --status
sonicradle --install
sonicradle --rebuild
```

`--status` onay, derleme veya kurulum bekleme durumunu gösterir. `--install`,
daha önce hazırlanmış RPM'nin SHA256 ve paket kimliğini yeniden doğrulayarak
kurulumu tekrar dener; yeniden DEB indirmez. `--rebuild` yeni yerel doğrulama/derleme ister; kullanıcı bilgisayarında ClamAV çalıştırmaz.
Yeni kaynak sürümü veya paketleme revizyonu yeniden onay gerektirir.

`--status` reports approval/build/install readiness. `--install` retries a
previously built RPM after checking its hash and package identity; it does not
repeat the DEB download. `--rebuild` requests a fresh local verification/build; it does not run ClamAV on the user host. New source
versions or bootstrap revisions need renewed approval.

Bu bağımsız kurucu gerçek LPF motorunu kullanmaz. Ayrı pkg-build hesabı ve LPF
bildirim servisi dahil mimari farklar [LPF karşılaştırmasında](docs/lpf-framework-audit.md)
açıklanır. This standalone installer does not use the actual LPF framework;
see the linked comparison for the account/lifecycle/notification differences.

## Sonicradle: stable / testing channel operations

```sh
sonicradle --setup
sonicradle --setup -unstable
sudo dnf upgrade --refresh sonicradle
sonicradle --update
sonicradle --update -unstable
sudo dnf remove sonicradle-client-local sonicradle
sudo dnf copr disable universish/Spotify..Client
```

`-unstable` is a Sonicradle option, not a DNF option or a second package name.
Setup/update without it selects stable, including a switch from testing back to
stable; that can install an older vendor version. Both channels replace the
same local target, so there is one installed client. Launching `sonicradle` runs
the installed selection. Run setup/update without sudo. If an LPF/vendor client
is already installed, review migration first rather than assuming coexistence.

`-unstable`, Sonicradle seçeneğidir; DNF seçeneği veya ayrı paket adı değildir.
Eki kullanmadan kurulum/güncelleme stable seçer; testing'den dönüş sürümü
düşürebilir. İki kanal aynı yerel paketin yerine geçer; aynı anda iki istemci
kurulmaz. Mevcut LPF/vendor kurulumundan geçiş ayrıca incelenmelidir.

Read the English [project history and operating guide](docs/project-history-and-operation.md),
[paste-ready COPR description](docs/copr-description.md) and
[current legal/naming review](docs/legal-review-2026-10-30.md). COPR hosting
does not transfer responsibility to Fedora. The root notice/license files in
the original timestamp manifest remain historical evidence; active installation
notices are in `bootstrap/NOTICE.txt` and `bootstrap/DISCLAIMER.txt`.
