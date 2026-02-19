#!/usr/bin/env bash
set -euo pipefail

require_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

install_pkg_debian() {
  local pkgs=("$@")
  sudo apt-get update -y
  sudo apt-get install -y "${pkgs[@]}"
}

ensure_python() {
  if require_cmd python3; then
    return 0
  fi
  if require_cmd apt-get; then
    install_pkg_debian python3
    return 0
  fi
  echo "python3 not found and no supported package manager detected" >&2
  exit 1
}

ensure_pip() {
  if require_cmd pip3; then
    return 0
  fi
  if require_cmd apt-get; then
    install_pkg_debian python3-pip
    return 0
  fi
  echo "pip3 not found and no supported package manager detected" >&2
  exit 1
}

ensure_ansible() {
  if require_cmd ansible-playbook; then
    return 0
  fi
  if require_cmd apt-get; then
    install_pkg_debian ansible
    return 0
  fi
  pip3 install --user ansible
}

ensure_terraform() {
  if require_cmd terraform; then
    return 0
  fi
  echo "terraform not found. Install terraform manually before running apply." >&2
}

echo "Checking requirements..."
ensure_python
ensure_pip
ensure_ansible
ensure_terraform

pip3 install --user -r "$(dirname "$0")/requirements.txt"

echo "Bootstrap complete."
