#!/usr/bin/env bash
# Build toolchain needed to cargo-build parry-guard from source.
# Linux distros ship minimal images without C toolchain + OpenSSL headers;
# macOS uses Xcode CLT so no extra packages are emitted there.

build_tools_for_os() {
  case "$1" in
    ubuntu|debian) echo "build-essential libssl-dev pkg-config curl" ;;
    fedora) echo "gcc gcc-c++ openssl-devel pkg-config curl" ;;
    *) echo "" ;;
  esac
}
