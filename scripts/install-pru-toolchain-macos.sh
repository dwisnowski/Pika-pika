#!/usr/bin/env bash
# Install TI PRU CGT 2.3.3 + PRU Software Support Package on macOS so
# `make -C pika/pru build` catches clpru errors before syncing to the BBB.
set -euo pipefail

TI_ROOT="${TI_ROOT:-$HOME/ti}"
CGT_PREFIX="${CGT_PREFIX:-$TI_ROOT/cgt-pru-2.3.3}"
CGT_HOME="$CGT_PREFIX/ti-cgt-pru_2.3.3"
SSP_DIR="$TI_ROOT/pru-software-support-package"
CGT_URL="https://dr-download.ti.com/software-development/ide-configuration-compiler-or-debugger/MD-FaNNGkDH7s/2.3.3/ti_cgt_pru_2.3.3_osx_installer.app.zip"
SSP_URL="https://git.ti.com/git/pru-software-support-package/pru-software-support-package.git"
WORKDIR="${TMPDIR:-/tmp}/pika-pru-cgt-install"

mkdir -p "$TI_ROOT" "$WORKDIR"
cd "$WORKDIR"

if [[ ! -x "$CGT_HOME/bin/clpru" ]]; then
  echo "Downloading TI PRU CGT 2.3.3 (macOS)..."
  curl -fL -o installer.zip "$CGT_URL"
  rm -rf ti_cgt_pru_2.3.3_osx_installer.app
  unzip -qo installer.zip
  echo "Installing to $CGT_PREFIX ..."
  ./ti_cgt_pru_2.3.3_osx_installer.app/Contents/MacOS/osx-x86_64 \
    --mode unattended --prefix "$CGT_PREFIX"
else
  echo "clpru already present: $CGT_HOME/bin/clpru"
fi

if [[ ! -d "$SSP_DIR/.git" ]]; then
  echo "Cloning PRU Software Support Package..."
  git clone --depth 1 "$SSP_URL" "$SSP_DIR"
else
  echo "SSP already present: $SSP_DIR"
fi

echo
echo "Installed:"
"$CGT_HOME/bin/clpru" -version | head -2
echo "  PRU_CGT=$CGT_HOME"
echo "  PRU_SSP=$SSP_DIR"
echo
echo "Verify with:"
echo "  make -C pika/pru check-toolchain"
echo "  make -C pika/pru build"
