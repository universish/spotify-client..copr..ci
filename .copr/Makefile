# COPR SCM: git, main, SRPM build method = make srpm.
# See docs/copr.md for the Fedora COPR licensing restriction before submission.
outdir ?= $(CURDIR)/output

.PHONY: srpm
srpm:
	@test -n "$(SPOTIFY_RELEASE)" || (echo 'Set SPOTIFY_RELEASE explicitly; use the GitHub workflow for automatic numbering.' >&2; exit 2)
	dnf -y install bash python3 curl dpkg clamav clamav-freshclam rpm-build binutils tar gzip coreutils desktop-file-utils
	bash src/build_once.sh stable "$(outdir)"
