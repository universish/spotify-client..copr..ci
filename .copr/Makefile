# COPR SCM: git, main, SRPM build method = make srpm.
# See docs/copr.md for the Fedora COPR licensing restriction before submission.
outdir ?= $(CURDIR)/output

.PHONY: srpm
srpm:
	@test -n "$(SPOTIFY_RELEASE)" || (echo 'Set SPOTIFY_RELEASE explicitly; use the GitHub workflow for automatic numbering.' >&2; exit 2)
	dnf -y install bash python3 curl dpkg clamav clamav-freshclam rpm-build binutils tar gzip coreutils desktop-file-utils
	mkdir -p "$(outdir)/metadata"
	SPOTIFY_METADATA_DIR="$(outdir)/metadata" python3 src/parser_debian_control_file.py stable spotify-client Version
	python3 tools/build_bootstrap.py "$(outdir)/metadata/spotify-client.stable.json" "$(outdir)"
