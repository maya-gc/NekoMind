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


PORTABLE = ("neko_controller.c", "neko_layout.c", "neko_protocol.c", "neko_avatar3d.c")


def run_firmware_tests(workdir: Path) -> subprocess.CompletedProcess:
    """Compile and run EVERY tests/test_*.c with the portable firmware sources.

    New firmware tests are picked up automatically (no runner to update).
    """
    compiler = find_c_compiler()
    if compiler is None:
        raise RuntimeError("Nenhum compilador C: instale gcc/clang ou `pip install ziglang`")
    main = FIRMWARE / "main"
    sources = [str(main / name) for name in PORTABLE if (main / name).is_file()]
    # Windows: o compilador pode marcar fopen como "inseguro" (CRT da MS).
    extra = ["-D_CRT_SECURE_NO_WARNINGS"] if os.name == "nt" else ["-lm"]
    out, err, code, args = "", "", 0, []
    for test in sorted((FIRMWARE / "tests").glob("test_*.c")):
        binary = exe(workdir / test.stem)
        subprocess.run(
            [*compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", f"-I{main}",
             str(test), *sources, *extra, "-o", str(binary)],
            check=True, capture_output=True, text=True,
        )
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120,
                                check=False)
        out += f"[{test.name}] " + result.stdout
        err += result.stderr
        args = result.args
        if result.returncode != 0:
            code = result.returncode
            break
    return subprocess.CompletedProcess(args, code, out, err)


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
