"""Actual Python encoder -> compiled C controller; synthetic recorder/backend."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.mac.protocol import encode_line
from tests.test_mac_bridge import Backend, Recorder, command, make_bridge, run_background


def test_python_telemetry_is_accepted_by_c_controller(tmp_path):
    if not shutil.which("cc"):
        pytest.skip("C host compiler unavailable")
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / "interop.c"
    source.write_text("""
#include <stdio.h>
#include "neko_controller.h"
static void send_noop(const char *line, void *p) {(void)line; (void)p;}
int main(void) {
    neko_controller_t controller;
    neko_controller_callbacks_t cb = {.send_line = send_noop};
    neko_controller_init_with_boot_nonce(&controller, &cb, "boot");
    neko_controller_touch(&controller, NEKO_TOUCH_START, 1000);
    char line[4096]; unsigned now = 1100;
    while (fgets(line, sizeof(line), stdin)) {
        int code = neko_controller_receive(&controller, line, now);
        printf("%d %d %s\\n", code, controller.voice_level, controller.journey_step);
        now += 250;
    }
    return 0;
}
""")
    fw = root / "iot/nekomind_firmware/main"
    binary = tmp_path / "interop"
    subprocess.run(
        [
            "cc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{fw}",
            str(source),
            str(fw / "neko_controller.c"),
            str(fw / "neko_protocol.c"),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
    )
    backend, recorder = Backend(), Recorder(tmp_path / "capture.raw")
    recorder.voice = lambda: {"level": 68, "clipping": False, "quality": "ok"}
    bridge = make_bridge(tmp_path, backend, recorder)
    try:
        bridge.handle(command("diagnose", "diag"))
        run_background(bridge)
        list(bridge.drain_events())
        ack = bridge.handle(command("start", "boot-1"))
        bridge.tick(force=True)
        bridge.wait_for_operations()
        telemetry = next(event for event in bridge.drain_events() if event.get("voice"))
        assert telemetry["request_id"] == "boot-1"
        assert isinstance(telemetry["journey"], dict)
        result = subprocess.run(
            [str(binary)],
            input=encode_line(ack) + encode_line(telemetry),
            capture_output=True,
            check=True,
        )
        assert result.stdout.decode().splitlines()[-1] == "0 68 capture"
        json.loads(encode_line(telemetry))
    finally:
        bridge.close()
