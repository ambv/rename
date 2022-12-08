import os
import pathlib
import random
import string
import subprocess
import tempfile
import time
from typing import Iterator

import pytest

from rename import run, selftest, Renamer


def make_name() -> str:
    alphabet = string.digits + string.ascii_uppercase
    return "RE_" + "".join(random.choice(alphabet) for _ in range(5))


@pytest.fixture(scope="module", params=["MS-DOS FAT16", "Case-sensitive HFS+"])
def fs(request: pytest.FixtureRequest) -> Iterator[str]:  # pragma: no cover
    os.chdir("/")

    proc = subprocess.run(
        args=[
            "hdiutil",
            "attach",
            "-nobrowse",
            "-nomount",
            "ram://65536",
        ],
        check=True,
        capture_output=True,
    )
    disk_id = proc.stdout.strip().decode("ascii")
    for i in range(10):
        time.sleep(i)
        proc = subprocess.run(
            args=["diskutil", "list", disk_id],
            capture_output=True,
        )
        if proc.returncode == 0:
            break
    else:
        raise SystemError(f"RAM disk {disk_id} not accessible after 10 retries.")

    name = make_name()
    proc = subprocess.run(
        args=["diskutil", "erasevolume", request.param, name, disk_id],
        check=True,
        capture_output=True,
    )

    yield "/Volumes/" + name

    os.chdir("/")
    proc = subprocess.run(
        args=["hdiutil", "eject", disk_id],
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def tmp_dir() -> Iterator[str]:
    prev_dir = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="pytest_", suffix=".rename") as td:
        os.chdir(td)
        yield td
        os.chdir(prev_dir)


def test_simple_copy(tmp_dir: str) -> None:
    td = pathlib.Path(tmp_dir)
    (td / "some source file").write_text("temp text")
    try:
        run(["--simple", "--copy", "source", "target", ".*"])
    except SystemExit as sysex:
        assert sysex.code == 0
        assert (td / "some source file").exists()
        assert (td / "some target file").exists()
    else:  # pragma: no cover
        raise SystemError("This should have exited early.")


def test_regex_copy(tmp_dir: str) -> None:
    td = pathlib.Path(tmp_dir)
    (td / "some source file").write_text("temp text")
    try:
        run(["--copy", "(.*)source(.*)", r"\1target\2"])
    except SystemExit as sysex:
        assert sysex.code == 0
        assert (td / "some source file").exists()
        assert (td / "some target file").exists()
    else:  # pragma: no cover
        raise SystemError("This should have exited early.")


def test_default_tmpdir() -> None:
    try:
        run(["--selftest"])
    except SystemExit as sysex:
        assert sysex.code == 0
    else:  # pragma: no cover
        raise SystemError("This should have exited early.")


def test_help() -> None:
    try:
        run(["--help"])
    except SystemExit as sysex:
        assert sysex.code == 0
    else:  # pragma: no cover
        raise SystemError("This should have exited early.")


def test_invalid_regex_ref() -> None:
    r = Renamer(test=True)
    assert r.rename_regex(".*", target=r"\(invalid)") != 0


def test_slash() -> None:
    r = Renamer(test=True)
    assert r.rename_regex("/(.*)", target=r"\1") == 0


def test_with_fs(fs: str) -> None:
    assert selftest(fs) == 0
