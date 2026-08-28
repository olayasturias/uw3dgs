#!/bin/sh
# Fetch the eight method repositories at their pinned commits and apply the
# local adaptations used for the study.
#
# Run from the repository root:   sh experiments/repro/bootstrap.sh
#
# Why this exists instead of `git submodule update --init --recursive`:
#   * gaussian-splatting, RUSplatting and others vendor or reference
#     SIBR_viewers -- thousands of files, not needed to train or evaluate, and
#     it contains paths longer than Windows MAX_PATH.
#   * RUSplatting's .gitmodules points at submodules that must never be
#     initialised; its rasterizer is vendored directly in the parent tree.
#   * UW-GS, 3D-UIR, RUSplatting and SeaFree-GS vendor their rasterizers, so a
#     recursive init would fail or fetch the wrong thing.
set -e

if [ ! -f .gitmodules ]; then
  echo "error: run this from the repository root" >&2
  exit 1
fi

# Windows: several upstream trees contain paths over MAX_PATH.
if [ "$(git config --get core.longpaths)" != "true" ]; then
  echo "note: enabling core.longpaths for this repository (Windows MAX_PATH)"
  git config core.longpaths true
fi

echo "== 1/3  top-level method repos at pinned commits =="
# NOT --depth 1: the pinned commits are older than current upstream HEAD, and
# a shallow fetch of the branch tip would not contain them.
git submodule update --init -- \
  methods/gaussian-splatting methods/seasplat methods/recgs \
  methods/water-splatting methods/UW-GS methods/3D-UIR \
  methods/RUSplatting methods/SeaFree-GS

echo "== 2/3  nested rasterizers (selective -- never --recursive) =="
# Only these three carry their rasterizer as a submodule; the rest vendor it.
( cd methods/gaussian-splatting && git submodule update --init -- \
    submodules/diff-gaussian-rasterization submodules/simple-knn submodules/fused-ssim )
( cd methods/seasplat && git submodule update --init -- \
    submodules/diff-gaussian-rasterization submodules/simple-knn )
( cd methods/recgs && git submodule update --init -- \
    submodules/diff-gaussian-rasterization submodules/simple-knn )
( cd methods/water-splatting && git submodule update --init )

echo "== 3/3  apply local adaptations =="
P="$(pwd)/experiments/repro/patches"
apply() {   # apply <repo-path> <patch-file>
  [ -f "$2" ] || return 0
  if git -C "$1" apply --check "$2" 2>/dev/null; then
    git -C "$1" apply "$2"
    echo "   applied $(basename "$(dirname "$2")")/$(basename "$2")"
  elif git -C "$1" apply --reverse --check "$2" 2>/dev/null; then
    echo "   already applied $(basename "$(dirname "$2")")/$(basename "$2")"
  else
    echo "   FAILED   $(basename "$(dirname "$2")")/$(basename "$2")" >&2
    exit 1
  fi
}

apply methods/seasplat                                        "$P/seasplat/parent.patch"
apply methods/seasplat/submodules/diff-gaussian-rasterization "$P/seasplat/rasterizer.patch"
apply methods/recgs                                           "$P/recgs/parent.patch"
apply methods/recgs/submodules/diff-gaussian-rasterization    "$P/recgs/rasterizer.patch"
apply methods/UW-GS                                           "$P/UW-GS/parent.patch"
apply methods/3D-UIR                                          "$P/3D-UIR/parent.patch"
apply methods/RUSplatting                                     "$P/RUSplatting/parent.patch"

# Binary excluded from the patch: a prebuilt linux .so that shadows the local build.
rm -f methods/RUSplatting/submodules/diff-gaussian-rasterization/dgr_rus/_C.cpython-38-x86_64-linux-gnu.so
rm -f methods/RUSplatting/submodules/diff-gaussian-rasterization/diff_gaussian_rasterization/_C.cpython-38-x86_64-linux-gnu.so

echo
echo "Done. Next: build the CUDA extensions (experiments/repro/build_extensions.bat)"
echo "and see experiments/SETUP.md for the environment."
