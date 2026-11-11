#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
test_binary="$(mktemp -t nekomind_firmware_test.XXXXXX)"
trap 'rm -f "$test_binary"' EXIT

cc -std=c11 -Wall -Wextra -Werror \
  -Imain \
  tests/test_neko_controller.c \
  main/neko_controller.c \
  main/neko_layout.c \
  main/neko_protocol.c \
  -o "$test_binary"

"$test_binary"

cc -std=c11 -O2 -Wall -Wextra -Werror \
  tests/test_avatar3d.c main/neko_avatar3d.c -lm -o "$test_binary"
"$test_binary"
