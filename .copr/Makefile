# COPR SCM: git, main, SRPM build method = make srpm.
# See docs/copr.md for the Fedora COPR licensing restriction before submission.
outdir ?= $(CURDIR)/output

.PHONY: srpm
srpm:
	dnf -y install bash python3 curl dpkg clamav clamav-freshclam rpm-build binutils tar gzip coreutils
	bash src/build_once.sh stable "$(outdir)"
