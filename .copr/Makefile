# Optional offline SRPM construction from an already scanned Actions catalog.
# The supported publishing path uploads the CI-built SRPM; COPR never downloads
# or scans Spotify payloads. No automatic SCM source discovery is performed.
outdir ?= $(CURDIR)/output
SCANNED_METADATA ?=
SPOT_FLY_LIGHT_RELEASE ?=
export outdir SCANNED_METADATA SPOT_FLY_LIGHT_RELEASE

.PHONY: srpm
srpm:
	@test -n "$$SCANNED_METADATA" && test -f "$$SCANNED_METADATA" || { echo 'Use the GitHub Actions workflow. Offline builds require SCANNED_METADATA pointing to its scanned source.json catalog.' >&2; exit 2; }
	@python3 -c 'import json, os, re; from pathlib import Path; release = os.environ["SPOT_FLY_LIGHT_RELEASE"]; catalog = json.loads(Path(os.environ["SCANNED_METADATA"]).read_text()); assert re.fullmatch("[1-9][0-9]*", release), "Set SPOT_FLY_LIGHT_RELEASE to the reserved positive revision"; assert set(catalog) == {"stable", "unstable"}, "A scanned stable and unstable catalog is required"'
	@command -v rpmbuild >/dev/null || { echo 'Install rpm-build in the build environment before this offline build.' >&2; exit 2; }
	python3 tools/build_bootstrap.py "$$SCANNED_METADATA" "$$outdir" --release "$$SPOT_FLY_LIGHT_RELEASE"
