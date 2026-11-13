"""Find a host C compiler for the firmware unit tests on any OS.

Order: ``$CC``, ``cc``, ``gcc``, ``clang`` and finally Zig's bundled clang
(``pip install ziglang``), which gives Windows a compiler without MSYS2.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

FIRMWARE = Path(__file__).resolve().parents[3] / "iot" / "nekomind_firmware"


def find_c_compiler() -> list[str] | None:
    env = os.environ.get("CC")
    if env:
        return shlex.split(env)
    for name in ("cc", "gcc", "clang"):
        if shutil.which(name):
            return [name]
    try:
        import ziglang  # noqa: F401
    except ImportError:
        return None
    return [sys.executable, "-m", "ziglang", "cc"]


def exe(path: Path) -> Path:
    return path.with_suffix(".exe") if os.name == "nt" else path


def run_firmware_tests(workdir: Path) -> subprocess.CompletedProcess:
    """Compile and run the firmware host tests (controller and 3D avatar renderer)."""
    compiler = find_c_compiler()
    if compiler is None:
        raise RuntimeError("Nenhum compilador C: instale gcc/clang ou `pip install ziglang`")
    main = FIRMWARE / "main"
    binary = exe(workdir / "nekomind_firmware_test")
    subprocess.run(
        [*compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", f"-I{main}",
         str(FIRMWARE / "tests" / "test_neko_controller.c"), str(main / "neko_controller.c"),
         str(main / "neko_layout.c"), str(main / "neko_protocol.c"), "-o", str(binary)],
        check=True, capture_output=True, text=True,
    )
    first = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120)
    if first.returncode != 0 or not (FIRMWARE / "tests" / "test_avatar3d.c").is_file():
        return first
    # Renderizador 3D da gatinha (Leandro, 11/11/2026): mesmo teste do test_firmware.sh.
    avatar = exe(workdir / "nekomind_avatar3d_test")
    # Windows: o compilador pode marcar fopen do teste como "inseguro" (CRT da MS).
    libm = ["-D_CRT_SECURE_NO_WARNINGS"] if os.name == "nt" else ["-lm"]
    subprocess.run(
        [*compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
         str(FIRMWARE / "tests" / "test_avatar3d.c"), str(main / "neko_avatar3d.c"),
         *libm, "-o", str(avatar)],
        check=True, capture_output=True, text=True,
    )
    second = subprocess.run([str(avatar)], capture_output=True, text=True, timeout=120)
    return subprocess.CompletedProcess(
        second.args, second.returncode, first.stdout + second.stdout, first.stderr + second.stderr)


def main() -> int:
    import tempfile

    compiler = find_c_compiler()
    print("Compilador:", " ".join(compiler) if compiler else "nenhum")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            result = run_firmware_tests(Path(tmp))
        except subprocess.CalledProcessError as exc:
            print("Comando:", " ".join(str(a) for a in exc.cmd))
            print(exc.stdout, exc.stderr)
            print("RESULTADO: FALHA NA COMPILACAO")
            return 1
        except RuntimeError as exc:
            print(f"RESULTADO: PULADO ({exc})")
            return 2
    print(result.stdout[-4000:], result.stderr[-2000:])
    print("RESULTADO:", "FIRMWARE OK" if result.returncode == 0 else "FIRMWARE FALHOU")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
