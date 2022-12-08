#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2011-present Łukasz Langa <lukasz@langa.pl>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Renames files using regular expression matching."""

#
# This utility should use no dependencies other than Python 3.7+.
#

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import sys
from typing import Any, Callable, NewType, TextIO

__version__ = "22.12.0"


MATCH_REGEX = re.compile(r"(\\)(\d+)")
MATCH_REGEX_BRACKETS = re.compile(r"(\\\()([^)]+)(\))")
TRANSFORM: dict[str, Callable[[str], str]] = {
    "": lambda x: x,
    "lower": lambda x: x.lower(),
    "upper": lambda x: x.upper(),
}

StatusCode = NewType("StatusCode", int)


class Renamer:
    def __init__(
        self,
        *,
        test: bool = False,
        case_insensitive: bool = False,
        xform: str = "",
        quiet: bool = False,
        copy: bool = False,
        index_first: int | str = 1,
        index_step: int | str = 1,
        index_digits: int | str = "auto",
        index_pad_with: str = "0",
    ):
        self.case_insensitive = case_insensitive
        self.copy = copy
        self.xform = xform
        self.test = test
        self.quiet = quiet
        self.index_first = int(index_first)
        self.index_step = int(index_step)
        self.index_digits = index_digits
        self.index_pad_with = index_pad_with
        self.targets: dict[str, list[str]] = {}

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Renamer:
        return cls(
            case_insensitive=args.case_insensitive,
            copy=args.copy,
            xform=args.xform or "",
            test=args.test,
            quiet=args.quiet,
            index_first=getattr(args, "index_first", 1),
            index_step=getattr(args, "index_step", 1),
            index_digits=getattr(args, "index_digits", "auto"),
            index_pad_with=getattr(args, "index_pad_with", "0"),
        )

    def rename_regex(
        self, regex: str, *, target: str, except_regex: str | None = None
    ) -> StatusCode:
        """Renames files based on a pair of regular expressions.

        Returns a non-zero status code on failure, outputting any error
        information to stderr.
        """
        DEVNULL = open(os.devnull, "w")
        stdout = DEVNULL if self.quiet else sys.stdout
        stderr = DEVNULL if self.quiet else sys.stderr
        try:
            self._rename(
                regex,
                target=target,
                except_regex=except_regex,
                stdout=stdout,
                stderr=stderr,
            )
            return StatusCode(0)
        except ValueError as exc:
            print(exc, file=stderr)
            return StatusCode(1)
        except Exception as exc:  # pragma: no cover
            # Unhandled exceptions, unexpected exceptions.
            # No test coverage for that.
            print(exc, file=stderr)
            return StatusCode(2)
        finally:
            DEVNULL.close()

    def rename_simple(
        self,
        regex: str,
        *,
        substring_from: str,
        substring_to: str,
        except_regex: str | None = None,
    ) -> StatusCode:
        """Renames files based on a pair of simple substrings.
        
        `substring_from` is what we're catching (what was before).
        `substring_to` is what we're replacing with (what will be after).

        Returns a non-zero status code on failure, outputting any error
        information to stderr.
        """
        DEVNULL = open(os.devnull, "w")
        stdout = DEVNULL if self.quiet else sys.stdout
        stderr = DEVNULL if self.quiet else sys.stderr
        try:
            self._rename(
                regex,
                substring_from=substring_from,
                substring_to=substring_to,
                except_regex=except_regex,
                stdout=stdout,
                stderr=stderr,
            )
            return StatusCode(0)
        except ValueError as exc:
            print(exc, file=stderr)
            return StatusCode(1)
        except Exception as exc:  # pragma: no cover
            # Unhandled exceptions, unexpected exceptions.
            # No test coverage for that.
            print(exc, file=stderr)
            return StatusCode(2)
        finally:
            DEVNULL.close()

    def _apply_match(
        self, match: re.Match[str], target: str, index: int, max_indexes: int
    ) -> str:
        move_to = target
        for prefix, num in MATCH_REGEX.findall(target):
            move_to = move_to.replace(prefix + num, match.group(int(num)))
        for prefix, ref, suffix in MATCH_REGEX_BRACKETS.findall(target):
            ref_string = prefix + ref + suffix
            try:
                replacement = match.group(int(ref))
            except ValueError:
                if ref.lower() != "index":
                    raise ValueError("Unknown special reference: `%s`" % ref)
                replacement = "%d" % self.index(index)
                if self.index_digits == "auto":
                    index_digits = int(math.log(self.index(max_indexes), 10)) + 1
                else:
                    index_digits = int(self.index_digits)
                pad_count = index_digits - len(replacement)
                if pad_count > 0:
                    replacement = "".join(
                        (self.index_pad_with * pad_count, replacement)
                    )
            move_to = move_to.replace(ref_string, replacement)
        return TRANSFORM[self.xform](move_to)

    def _apply_replace(
        self, match: re.Match[str], substring_from: str, substring_to: str
    ) -> str:
        substring_from = re.escape(substring_from)
        if not self.case_insensitive:
            sub = re.compile(substring_from)
        else:
            sub = re.compile(substring_from, re.IGNORECASE)
        move_to = sub.sub(substring_to, match.group())
        return TRANSFORM[self.xform](move_to)

    def index(self, number: int) -> int:
        return self.index_first + (number * self.index_step)

    def _rename(
        self,
        regex: str,
        *,
        target: str | None = None,
        except_regex: str | None = None,
        substring_from: str | None = None,
        substring_to: str | None = None,
        stdout: TextIO = sys.stdout,
        stderr: TextIO = sys.stderr,
    ) -> None:
        """Does the actual renaming given the parameters.

        Raises an exception on first failure and doesn't proceed.
        In case `test=True` is set on the object, uses `stdout` to
        output what it would do.  In case of non-fatal anomalies
        outputs warnings to `stderr`.
        """
        flags = 0
        if self.case_insensitive:
            flags = re.IGNORECASE
        r = re.compile("^%s$" % regex, flags)
        for string in [
            "regex",
            "target",
            "except_regex",
            "substring_from",
            "substring_to",
        ]:
            value = locals()[string]
            if value and os.sep in value:
                print(
                    f"warning: {os.sep} found in <{string}> but"
                    f" this tool doesn't support directory traversal.",
                    file=stderr,
                )
        exc = None
        if except_regex:
            exc = re.compile(except_regex, flags)
        index = 0
        files = os.listdir(".")
        if exc:
            files = [f for f in files if not exc.search(f)]
        file_count = len(files)
        for index, entry in enumerate(files):
            m = r.search(entry)
            if not m:
                continue
            if target is not None:
                # classic regex mode
                move_to = self._apply_match(m, target, index, file_count)
            elif substring_from is not None and substring_to is not None:
                # simple mode
                move_to = self._apply_replace(m, substring_from, substring_to)
            else:  # pragma: no cover
                # should not happen as argparse sanitized inputs already
                raise RuntimeError(
                    f"Invalid method state: target={target}"
                    f" substring_from={substring_from}"
                    f" substring_to={substring_to}"
                )
            self.targets.setdefault(move_to, []).append(entry)
        # sanity check
        for target, sources in self.targets.items():
            if len(sources) > 1:
                files = ", ".join(sources)
                raise ValueError(
                    f"Multiple files ({files}) would be written to {target}"
                )
            if os.path.exists(target) and not is_same_file(target, sources[0]):
                raise ValueError(
                    f"Target {target} already exists for source {sources[0]}"
                )
        # actual rename
        for target, sources in self.targets.items():
            if sources[0] == target:
                if self.test:
                    print(
                        f"note: file {sources[0]} matches but name doesn't change.",
                        file=stderr,
                    )
                continue
            if self.copy:
                if self.test:
                    print(
                        f"Would run shutil.copy{sources[0], target} (with copymode"
                        f" and copystat)",
                        file=stdout,
                    )
                else:
                    shutil.copy(sources[0], target)
                    shutil.copymode(sources[0], target)
                    shutil.copystat(sources[0], target)
            else:
                if self.test:
                    print(f"Would run os.rename{sources[0], target}", file=stdout)
                else:
                    os.rename(sources[0], target)


def is_same_file(file1: str, file2: str) -> bool:
    return (
        os.path.abspath(file1).lower() == os.path.abspath(file2).lower()
        and os.stat(file1).st_ino == os.stat(file2).st_ino
    )


class ProxyMember:
    def __init__(self, name: str, targets: tuple[object, ...]) -> None:
        self.name = name
        self.targets = targets

    def __call__(self, *args: Any, **kwargs: Any) -> list[Any]:
        result: list[Any] = []
        for target in self.targets:
            result.append(getattr(target, self.name)(*args, **kwargs))
        return result


class Proxy:
    def __init__(self, *targets: object) -> None:
        self.targets = targets

    def __getattr__(self, name: str) -> Any:
        return ProxyMember(name, self.targets)


class SentinelStr(str):
    """A special string that the user cannot ever pass."""


use_tmp = SentinelStr("use_tmp")


def run(cmdline_args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rename", add_help=False)
    classic = argparse.ArgumentParser(prog="rename")
    simple = argparse.ArgumentParser(prog="rename")
    invocator = Proxy(classic, parser)

    simple.add_argument(
        "-s",
        "--simple",
        action="store_true",
        help="invokes the simple mode",
        required=True,
    )
    common = Proxy(classic, simple)
    common.add_argument(
        "-c", "--copy", action="store_true", help="copy files instead of renaming"
    )
    common.add_argument(
        "-i",
        "-I",
        "--case-insensitive",
        action="store_true",
        help="treat the regular expression as case-insensitive",
    )
    common.add_argument(
        "-l",
        "--lower",
        action="store_const",
        dest="xform",
        const="lower",
        help="translate all letters to lower-case",
    )
    common.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="don't print anything, just return status codes",
    )
    common.add_argument(
        "-U",
        "--upper",
        action="store_const",
        dest="xform",
        const="upper",
        help="translate all letters to upper-case",
    )
    common.add_argument(
        "-v",
        "--except",
        dest="except_regex",
        action="store",
        default="",
        help="exclude files matching the following regular expression",
    )
    common.add_argument(
        "-t",
        "--test",
        action="store_true",
        help="test only, don't actually rename anything",
    )
    group = classic.add_argument_group(
        "Configuration for the special \\(index) reference"
    )
    group.add_argument(
        "--index-first",
        default=1,
        help="specifies "
        "what number will the first \\(index) substitution contain. Default: 1",
    )
    group.add_argument(
        "--index-step",
        default=1,
        help="specifies "
        "what number will be added with each step to the first value. Negative "
        "numbers allowed. Default: 1",
    )
    group.add_argument(
        "--index-digits",
        default="auto",
        help="specifies how many digits will be used in each \\(index) "
        "substitution. If a number has fewer digits, they will be prefixed by "
        "leading zeroes (or another character, see --index-pad-with). Default: "
        "auto (e.g. path enough digits so that each number uses the same amount"
        " of characters)",
    )
    group.add_argument(
        "--index-pad-with",
        default="0",
        help='specifies what character will be used for padding. Default: "0"',
    )
    invocator.add_argument(
        "-s",
        "--simple",
        action="store_true",
        help="invokes "
        "the simple mode. For more help on its positional arguments: "
        "rename -s --help",
    )
    invocator.add_argument(
        "--selftest",
        nargs="?",
        const=use_tmp,
        metavar="use_directory",
        help="run internal unit tests",
    )
    classic.add_argument("regex", help="regular expression to match files with")
    classic.add_argument(
        "target",
        help="target pattern using references to groups in the regular expression",
    )
    simple.add_argument(
        "substring_from",
        help="simple (raw) substring that should be found within the filename",
    )
    simple.add_argument("substring_to", help="the replacement string")
    simple.add_argument("regex", help="regular expression to match files with")
    known_args, _rest = parser.parse_known_args(cmdline_args)
    if known_args.selftest:
        status_code = selftest(known_args.selftest)
    elif known_args.simple:
        args = simple.parse_args(cmdline_args)
        renamer = Renamer.from_args(args)
        status_code = renamer.rename_simple(
            regex="".join(args.regex),
            substring_from="".join(args.substring_from),
            substring_to="".join(args.substring_to),
            except_regex="".join(args.except_regex),
        )
    else:
        args = classic.parse_args(cmdline_args)
        renamer = Renamer.from_args(args)
        status_code = renamer.rename_regex(
            regex="".join(args.regex),
            target="".join(args.target),
            except_regex="".join(args.except_regex),
        )
    sys.exit(status_code)


CASE_SENSITIVE = StatusCode(60)
CASE_PRESERVING = StatusCode(30)
CASE_INSENSITIVE = StatusCode(-30)


def selftest(temp_dir: str = use_tmp) -> StatusCode:
    if temp_dir is use_tmp:
        temp_dir = ""

    test_count = 0
    failures = 0

    def _runtest(
        testcase: Callable[[], StatusCode], show_dir: bool = False
    ) -> StatusCode:
        import tempfile

        dirpath = tempfile.mkdtemp(".selftest", "rename_", temp_dir or None)
        if show_dir:
            print(
                "Using", os.path.split(dirpath)[0], "as the temporary directory base."
            )
        try:
            for prefix in ("CaSe", "case"):
                for index in range(1, 4):
                    for suffix in "qwertyuiop":
                        path = "".join([dirpath, os.sep, prefix, str(index), suffix])
                        try:
                            f = open(path, "w")
                            try:
                                f.write(path)
                                f.write("\r\n")
                            finally:
                                f.close()
                        except OSError:  # pragma: no cover
                            print(
                                "Cannot create temporary file:",
                                path,
                                file=sys.stderr,
                            )
                            sys.exit(1)
            cwd = os.getcwd()
            os.chdir(dirpath)
            try:
                return testcase()
            finally:
                os.chdir(cwd)
        finally:
            files = os.listdir(dirpath)
            for fn in files:
                os.unlink(os.sep.join((dirpath, fn)))
            os.rmdir(dirpath)

    def test_fs_case() -> StatusCode:
        files = os.listdir(".")
        if len(files) == 60:
            print("Testing on a case-sensitive filesystem.")
            return CASE_SENSITIVE
        elif len(files) == 30:
            preserving = all([f.startswith("CaSe") for f in files])
            if preserving:
                print("Testing on a case-preserving filesystem.")
                return CASE_PRESERVING
            else:  # pragma: no cover
                # Extremely unlikely, only FAT12 and FAT16 without
                # long filename support are truly case insensitive.
                print("Testing on a case-insensitive filesystem.")
                return CASE_INSENSITIVE
        else:  # pragma: no cover
            print(
                (
                    "Not all files were created successfully. "
                    "Expected 60 or 30, got %d." % len(files)
                ),
                file=sys.stderr,
            )
            return StatusCode(10)

    def _runcase(
        *,
        desc: str,
        files: set[str] = set(),
        result: StatusCode = StatusCode(0),
        renamer: Renamer | None = None,
        simple: bool = False,
        regex: str = "",
        target: str = "",
        substring_from: str = "",
        substring_to: str = "",
        except_regex: str | None = None,
    ) -> None:
        nonlocal failures
        nonlocal test_count
        test_count += 1

        def case() -> StatusCode:  # pragma: no cover
            r = renamer or Renamer()

            # sanity checks first, no real renames performed
            r.test = True
            r.quiet = True
            try:
                if simple:
                    actual_result = r.rename_simple(
                        regex,
                        substring_from=substring_from,
                        substring_to=substring_to,
                        except_regex=except_regex,
                    )
                else:
                    actual_result = r.rename_regex(
                        regex,
                        target=target,
                        except_regex=except_regex,
                    )
                if actual_result != 0 and actual_result != result:
                    raise ValueError(actual_result)
            except ValueError as e:
                print(
                    f"Test {test_count} ({desc}) failed ({e}).",
                    file=sys.stderr,
                )
                return StatusCode(e.args[0])
            except Exception as e:
                print(
                    f"Test {test_count} ({desc}) failed (12): {e}.",
                    file=sys.stderr,
                )
                return StatusCode(12)

            # now actual renames on the file system
            r.test = False
            r.quiet = False
            r.targets = {}
            try:
                if simple:
                    actual_result = r.rename_simple(
                        regex,
                        substring_from=substring_from,
                        substring_to=substring_to,
                        except_regex=except_regex,
                    )
                else:
                    actual_result = r.rename_regex(
                        regex,
                        target=target,
                        except_regex=except_regex,
                    )
                if actual_result != result:
                    raise ValueError(result)
                actual_files = set(os.listdir("."))
                if actual_result == 0 and actual_files != files:
                    extra_files = actual_files - files
                    missing_files = files - actual_files
                    if extra_files:
                        print("Extra files:", extra_files)
                    if missing_files:
                        print("Missing files:", missing_files)
                    raise ValueError(11)
                print(f"Test {test_count} OK.")
                return StatusCode(0)
            except ValueError as e:
                print(
                    f"Test {test_count} ({desc}) failed ({e}).",
                    file=sys.stderr,
                )
                return StatusCode(e.args[0])
            except Exception as e:
                print(
                    f"Test {test_count} ({desc}) failed (12): {e}.",
                    file=sys.stderr,
                )
                return StatusCode(12)

        failures += _runtest(case)

    def _case_sensitive_tests() -> None:
        _runcase(
            desc="CaSe -> BrandNew",
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"BrandNew\1",
            files={
                "BrandNew1e",
                "BrandNew1i",
                "BrandNew1o",
                "BrandNew1p",
                "BrandNew1q",
                "BrandNew1r",
                "BrandNew1t",
                "BrandNew1u",
                "BrandNew1w",
                "BrandNew1y",
                "BrandNew2e",
                "BrandNew2i",
                "BrandNew2o",
                "BrandNew2p",
                "BrandNew2q",
                "BrandNew2r",
                "BrandNew2t",
                "BrandNew2u",
                "BrandNew2w",
                "BrandNew2y",
                "BrandNew3e",
                "BrandNew3i",
                "BrandNew3o",
                "BrandNew3p",
                "BrandNew3q",
                "BrandNew3r",
                "BrandNew3t",
                "BrandNew3u",
                "BrandNew3w",
                "BrandNew3y",
                "case1e",
                "case1i",
                "case1o",
                "case1p",
                "case1q",
                "case1r",
                "case1t",
                "case1u",
                "case1w",
                "case1y",
                "case2e",
                "case2i",
                "case2o",
                "case2p",
                "case2q",
                "case2r",
                "case2t",
                "case2u",
                "case2w",
                "case2y",
                "case3e",
                "case3i",
                "case3o",
                "case3p",
                "case3q",
                "case3r",
                "case3t",
                "case3u",
                "case3w",
                "case3y",
            },
        )
        _runcase(
            desc="CaSe -> case",
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"case\1",
            result=StatusCode(1),
        )
        _runcase(
            desc="CaSe (i) -> case",
            renamer=Renamer(case_insensitive=True),
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"case\1",
            result=StatusCode(1),
        )
        _runcase(
            desc="[Cc][Aa][Ss][Ee] -> case",
            renamer=Renamer(case_insensitive=True),
            regex=r"[Cc][Aa][Ss][Ee](\d[qwertyuiop])",
            target=r"case\1",
            result=StatusCode(1),
        )
        _runcase(
            desc="CaSe -> SeCa (except e$)",
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"SeCa\1",
            except_regex=r"e$",
            files={
                "CaSe1e",
                "SeCa1i",
                "SeCa1o",
                "SeCa1p",
                "SeCa1q",
                "SeCa1r",
                "SeCa1t",
                "SeCa1u",
                "SeCa1w",
                "SeCa1y",
                "CaSe2e",
                "SeCa2i",
                "SeCa2o",
                "SeCa2p",
                "SeCa2q",
                "SeCa2r",
                "SeCa2t",
                "SeCa2u",
                "SeCa2w",
                "SeCa2y",
                "CaSe3e",
                "SeCa3i",
                "SeCa3o",
                "SeCa3p",
                "SeCa3q",
                "SeCa3r",
                "SeCa3t",
                "SeCa3u",
                "SeCa3w",
                "SeCa3y",
                "case1e",
                "case1i",
                "case1o",
                "case1p",
                "case1q",
                "case1r",
                "case1t",
                "case1u",
                "case1w",
                "case1y",
                "case2e",
                "case2i",
                "case2o",
                "case2p",
                "case2q",
                "case2r",
                "case2t",
                "case2u",
                "case2w",
                "case2y",
                "case3e",
                "case3i",
                "case3o",
                "case3p",
                "case3q",
                "case3r",
                "case3t",
                "case3u",
                "case3w",
                "case3y",
            },
        )
        _runcase(
            desc="CaSe -> SeCa (U)",
            renamer=Renamer(xform="upper"),
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"SeCa\1",
            except_regex=r"e$",
            files={
                "CaSe1e",
                "SECA1I",
                "SECA1O",
                "SECA1P",
                "SECA1Q",
                "SECA1R",
                "SECA1T",
                "SECA1U",
                "SECA1W",
                "SECA1Y",
                "CaSe2e",
                "SECA2I",
                "SECA2O",
                "SECA2P",
                "SECA2Q",
                "SECA2R",
                "SECA2T",
                "SECA2U",
                "SECA2W",
                "SECA2Y",
                "CaSe3e",
                "SECA3I",
                "SECA3O",
                "SECA3P",
                "SECA3Q",
                "SECA3R",
                "SECA3T",
                "SECA3U",
                "SECA3W",
                "SECA3Y",
                "case1e",
                "case1i",
                "case1o",
                "case1p",
                "case1q",
                "case1r",
                "case1t",
                "case1u",
                "case1w",
                "case1y",
                "case2e",
                "case2i",
                "case2o",
                "case2p",
                "case2q",
                "case2r",
                "case2t",
                "case2u",
                "case2w",
                "case2y",
                "case3e",
                "case3i",
                "case3o",
                "case3p",
                "case3q",
                "case3r",
                "case3t",
                "case3u",
                "case3w",
                "case3y",
            },
        )
        _runcase(
            desc="CaSe (i) -> SeCa (U)",
            renamer=Renamer(case_insensitive=True, xform="upper"),
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"SeCa\1",
            except_regex=r"e$",
            result=StatusCode(1),
        )
        _runcase(
            desc="CaSe -> index (auto)",
            renamer=Renamer(case_insensitive=True),
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"C\(index)",
            files={"C{0:0>2}".format(i + 1) for i in range(60)},
        )
        _runcase(
            desc="CaSe -> index (100, +2, _, auto)",
            renamer=Renamer(
                case_insensitive=True, index_first=100, index_step=2, index_pad_with="_"
            ),
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"C\(index)",
            files={"C{0:_>3}".format(i) for i in range(100, 220, 2)},
        )
        _runcase(
            desc="CaSe -> index (100, +2, _, 5)",
            renamer=Renamer(
                case_insensitive=True,
                copy=True,
                index_first=100,
                index_step=2,
                index_pad_with="_",
                index_digits=5,
            ),
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"C\(index)",
            files={"C{0:_>5}".format(i) for i in range(100, 220, 2)}
            | {
                f"{prefix}{index}{suffix}"
                for prefix in ("CaSe", "case")
                for index in range(1, 4)
                for suffix in "qwertyuiop"
            },
        )
        _runcase(
            desc="CaSe -> replace `e` with `ee`",
            simple=True,
            regex=r"CaSe(\d[qwertyuiop])",
            substring_from="e",
            substring_to="ee",
            files={
                "CaSee1ee",
                "CaSee1i",
                "CaSee1o",
                "CaSee1p",
                "CaSee1q",
                "CaSee1r",
                "CaSee1t",
                "CaSee1u",
                "CaSee1w",
                "CaSee1y",
                "CaSee2ee",
                "CaSee2i",
                "CaSee2o",
                "CaSee2p",
                "CaSee2q",
                "CaSee2r",
                "CaSee2t",
                "CaSee2u",
                "CaSee2w",
                "CaSee2y",
                "CaSee3ee",
                "CaSee3i",
                "CaSee3o",
                "CaSee3p",
                "CaSee3q",
                "CaSee3r",
                "CaSee3t",
                "CaSee3u",
                "CaSee3w",
                "CaSee3y",
                "case1e",
                "case1i",
                "case1o",
                "case1p",
                "case1q",
                "case1r",
                "case1t",
                "case1u",
                "case1w",
                "case1y",
                "case2e",
                "case2i",
                "case2o",
                "case2p",
                "case2q",
                "case2r",
                "case2t",
                "case2u",
                "case2w",
                "case2y",
                "case3e",
                "case3i",
                "case3o",
                "case3p",
                "case3q",
                "case3r",
                "case3t",
                "case3u",
                "case3w",
                "case3y",
            },
        )
        _runcase(
            desc="CaSe (i) -> replace `e` with `ee`",
            simple=True,
            renamer=Renamer(case_insensitive=True),
            regex=r"CaSe(\d[qwertyuiop])",
            substring_from="e",
            substring_to="ee",
            files={
                "CaSee1ee",
                "CaSee1i",
                "CaSee1o",
                "CaSee1p",
                "CaSee1q",
                "CaSee1r",
                "CaSee1t",
                "CaSee1u",
                "CaSee1w",
                "CaSee1y",
                "CaSee2ee",
                "CaSee2i",
                "CaSee2o",
                "CaSee2p",
                "CaSee2q",
                "CaSee2r",
                "CaSee2t",
                "CaSee2u",
                "CaSee2w",
                "CaSee2y",
                "CaSee3ee",
                "CaSee3i",
                "CaSee3o",
                "CaSee3p",
                "CaSee3q",
                "CaSee3r",
                "CaSee3t",
                "CaSee3u",
                "CaSee3w",
                "CaSee3y",
                "casee1ee",
                "casee1i",
                "casee1o",
                "casee1p",
                "casee1q",
                "casee1r",
                "casee1t",
                "casee1u",
                "casee1w",
                "casee1y",
                "casee2ee",
                "casee2i",
                "casee2o",
                "casee2p",
                "casee2q",
                "casee2r",
                "casee2t",
                "casee2u",
                "casee2w",
                "casee2y",
                "casee3ee",
                "casee3i",
                "casee3o",
                "casee3p",
                "casee3q",
                "casee3r",
                "casee3t",
                "casee3u",
                "casee3w",
                "casee3y",
            },
        )
        _runcase(
            desc="CaSe (i) -> (U) replace `e` with `ee`",
            simple=True,
            renamer=Renamer(case_insensitive=True, xform="upper"),
            regex=r"CaSe(\d[qwertyuiop])",
            substring_from="e",
            substring_to="ee",
            result=StatusCode(1),
        )
        _runcase(
            desc="CaSe (i) -> replace `e` with `ee` (except e$)",
            simple=True,
            renamer=Renamer(case_insensitive=True),
            regex=r"CaSe(\d[qwertyuiop])",
            substring_from="e",
            substring_to="ee",
            except_regex=r"e$",
            files={
                "CaSe1e",
                "CaSee1i",
                "CaSee1o",
                "CaSee1p",
                "CaSee1q",
                "CaSee1r",
                "CaSee1t",
                "CaSee1u",
                "CaSee1w",
                "CaSee1y",
                "CaSe2e",
                "CaSee2i",
                "CaSee2o",
                "CaSee2p",
                "CaSee2q",
                "CaSee2r",
                "CaSee2t",
                "CaSee2u",
                "CaSee2w",
                "CaSee2y",
                "CaSe3e",
                "CaSee3i",
                "CaSee3o",
                "CaSee3p",
                "CaSee3q",
                "CaSee3r",
                "CaSee3t",
                "CaSee3u",
                "CaSee3w",
                "CaSee3y",
                "case1e",
                "casee1i",
                "casee1o",
                "casee1p",
                "casee1q",
                "casee1r",
                "casee1t",
                "casee1u",
                "casee1w",
                "casee1y",
                "case2e",
                "casee2i",
                "casee2o",
                "casee2p",
                "casee2q",
                "casee2r",
                "casee2t",
                "casee2u",
                "casee2w",
                "casee2y",
                "case3e",
                "casee3i",
                "casee3o",
                "casee3p",
                "casee3q",
                "casee3r",
                "casee3t",
                "casee3u",
                "casee3w",
                "casee3y",
            },
        )

    def _case_preserving_tests() -> None:
        _runcase(
            desc="CaSe -> BrandNew",
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"BrandNew\1",
            files={
                "BrandNew1e",
                "BrandNew1i",
                "BrandNew1o",
                "BrandNew1p",
                "BrandNew1q",
                "BrandNew1r",
                "BrandNew1t",
                "BrandNew1u",
                "BrandNew1w",
                "BrandNew1y",
                "BrandNew2e",
                "BrandNew2i",
                "BrandNew2o",
                "BrandNew2p",
                "BrandNew2q",
                "BrandNew2r",
                "BrandNew2t",
                "BrandNew2u",
                "BrandNew2w",
                "BrandNew2y",
                "BrandNew3e",
                "BrandNew3i",
                "BrandNew3o",
                "BrandNew3p",
                "BrandNew3q",
                "BrandNew3r",
                "BrandNew3t",
                "BrandNew3u",
                "BrandNew3w",
                "BrandNew3y",
            },
        )
        _runcase(
            desc="CaSe -> case",
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"case\1",
            files={
                "case1e",
                "case1i",
                "case1o",
                "case1p",
                "case1q",
                "case1r",
                "case1t",
                "case1u",
                "case1w",
                "case1y",
                "case2e",
                "case2i",
                "case2o",
                "case2p",
                "case2q",
                "case2r",
                "case2t",
                "case2u",
                "case2w",
                "case2y",
                "case3e",
                "case3i",
                "case3o",
                "case3p",
                "case3q",
                "case3r",
                "case3t",
                "case3u",
                "case3w",
                "case3y",
            },
        )
        _runcase(
            desc="CaSe (i) -> CAse",
            renamer=Renamer(case_insensitive=True),
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"CAse\1",
            files={
                "CAse1e",
                "CAse1i",
                "CAse1o",
                "CAse1p",
                "CAse1q",
                "CAse1r",
                "CAse1t",
                "CAse1u",
                "CAse1w",
                "CAse1y",
                "CAse2e",
                "CAse2i",
                "CAse2o",
                "CAse2p",
                "CAse2q",
                "CAse2r",
                "CAse2t",
                "CAse2u",
                "CAse2w",
                "CAse2y",
                "CAse3e",
                "CAse3i",
                "CAse3o",
                "CAse3p",
                "CAse3q",
                "CAse3r",
                "CAse3t",
                "CAse3u",
                "CAse3w",
                "CAse3y",
            },
        )
        _runcase(
            desc="[Cc][Aa][Ss][Ee] -> caSE",
            regex=r"[Cc][Aa][Ss][Ee](\d[qwertyuiop])",
            target=r"caSE\1",
            renamer=Renamer(case_insensitive=True),
            files={
                "caSE1e",
                "caSE1i",
                "caSE1o",
                "caSE1p",
                "caSE1q",
                "caSE1r",
                "caSE1t",
                "caSE1u",
                "caSE1w",
                "caSE1y",
                "caSE2e",
                "caSE2i",
                "caSE2o",
                "caSE2p",
                "caSE2q",
                "caSE2r",
                "caSE2t",
                "caSE2u",
                "caSE2w",
                "caSE2y",
                "caSE3e",
                "caSE3i",
                "caSE3o",
                "caSE3p",
                "caSE3q",
                "caSE3r",
                "caSE3t",
                "caSE3u",
                "caSE3w",
                "caSE3y",
            },
        )
        _runcase(
            desc="CaSe -> SeCa (except e$)",
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"SeCa\1",
            except_regex=r"e$",
            files={
                "CaSe1e",
                "SeCa1i",
                "SeCa1o",
                "SeCa1p",
                "SeCa1q",
                "SeCa1r",
                "SeCa1t",
                "SeCa1u",
                "SeCa1w",
                "SeCa1y",
                "CaSe2e",
                "SeCa2i",
                "SeCa2o",
                "SeCa2p",
                "SeCa2q",
                "SeCa2r",
                "SeCa2t",
                "SeCa2u",
                "SeCa2w",
                "SeCa2y",
                "CaSe3e",
                "SeCa3i",
                "SeCa3o",
                "SeCa3p",
                "SeCa3q",
                "SeCa3r",
                "SeCa3t",
                "SeCa3u",
                "SeCa3w",
                "SeCa3y",
            },
        )
        _runcase(
            desc="CaSe -> SeCa (U)",
            renamer=Renamer(xform="upper"),
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"SeCa\1",
            except_regex=r"e$",
            files={
                "CaSe1e",
                "SECA1I",
                "SECA1O",
                "SECA1P",
                "SECA1Q",
                "SECA1R",
                "SECA1T",
                "SECA1U",
                "SECA1W",
                "SECA1Y",
                "CaSe2e",
                "SECA2I",
                "SECA2O",
                "SECA2P",
                "SECA2Q",
                "SECA2R",
                "SECA2T",
                "SECA2U",
                "SECA2W",
                "SECA2Y",
                "CaSe3e",
                "SECA3I",
                "SECA3O",
                "SECA3P",
                "SECA3Q",
                "SECA3R",
                "SECA3T",
                "SECA3U",
                "SECA3W",
                "SECA3Y",
            },
        )
        _runcase(
            desc="CaSe (i) -> SeCa (U)",
            renamer=Renamer(case_insensitive=True, xform="upper"),
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"SeCa\1",
            except_regex=r"e$",
            files={
                "CaSe1e",
                "SECA1I",
                "SECA1O",
                "SECA1P",
                "SECA1Q",
                "SECA1R",
                "SECA1T",
                "SECA1U",
                "SECA1W",
                "SECA1Y",
                "CaSe2e",
                "SECA2I",
                "SECA2O",
                "SECA2P",
                "SECA2Q",
                "SECA2R",
                "SECA2T",
                "SECA2U",
                "SECA2W",
                "SECA2Y",
                "CaSe3e",
                "SECA3I",
                "SECA3O",
                "SECA3P",
                "SECA3Q",
                "SECA3R",
                "SECA3T",
                "SECA3U",
                "SECA3W",
                "SECA3Y",
            },
        )
        _runcase(
            desc="CaSe -> index (auto)",
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"C\(index)",
            files={"C{0:0>2}".format(i + 1) for i in range(30)},
        )
        _runcase(
            desc="CaSe -> index (100, +2, _, auto)",
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"C\(index)",
            renamer=Renamer(index_first=100, index_step=2, index_pad_with="_"),
            files={"C{0:_>3}".format(i) for i in range(100, 160, 2)},
        )
        _runcase(
            desc="CaSe -> index (100, +2, _, 5)",
            renamer=Renamer(
                case_insensitive=True,
                copy=True,
                index_first=100,
                index_step=2,
                index_pad_with="_",
                index_digits=5,
            ),
            regex=r"CaSe(\d[qwertyuiop])",
            target=r"C\(index)",
            files={"C{0:_>5}".format(i) for i in range(100, 160, 2)}
            | {
                f"CaSe{index}{suffix}"
                for index in range(1, 4)
                for suffix in "qwertyuiop"
            },
        )
        _runcase(
            desc="CaSe -> replace `e` with `ee`",
            simple=True,
            regex=r"CaSe(\d[qwertyuiop])",
            substring_from="e",
            substring_to="ee",
            files={
                "CaSee1ee",
                "CaSee1i",
                "CaSee1o",
                "CaSee1p",
                "CaSee1q",
                "CaSee1r",
                "CaSee1t",
                "CaSee1u",
                "CaSee1w",
                "CaSee1y",
                "CaSee2ee",
                "CaSee2i",
                "CaSee2o",
                "CaSee2p",
                "CaSee2q",
                "CaSee2r",
                "CaSee2t",
                "CaSee2u",
                "CaSee2w",
                "CaSee2y",
                "CaSee3ee",
                "CaSee3i",
                "CaSee3o",
                "CaSee3p",
                "CaSee3q",
                "CaSee3r",
                "CaSee3t",
                "CaSee3u",
                "CaSee3w",
                "CaSee3y",
            },
        )
        _runcase(
            desc="CaSe -> replace `e` with `ee` (except e$)",
            simple=True,
            regex=r"CaSe(\d[qwertyuiop])",
            substring_from="e",
            substring_to="ee",
            except_regex=r"e$",
            files={
                "CaSe1e",
                "CaSee1i",
                "CaSee1o",
                "CaSee1p",
                "CaSee1q",
                "CaSee1r",
                "CaSee1t",
                "CaSee1u",
                "CaSee1w",
                "CaSee1y",
                "CaSe2e",
                "CaSee2i",
                "CaSee2o",
                "CaSee2p",
                "CaSee2q",
                "CaSee2r",
                "CaSee2t",
                "CaSee2u",
                "CaSee2w",
                "CaSee2y",
                "CaSe3e",
                "CaSee3i",
                "CaSee3o",
                "CaSee3p",
                "CaSee3q",
                "CaSee3r",
                "CaSee3t",
                "CaSee3u",
                "CaSee3w",
                "CaSee3y",
            },
        )
        _runcase(
            desc="CaSe -> replace `cAs` with `Fac`",
            simple=True,
            regex=r"CaSe(\d[qwertyuiop])",
            substring_from="cAs",
            substring_to="Fac",
            except_regex=r"e$",
            files={
                "CaSe1e",
                "CaSe1i",
                "CaSe1o",
                "CaSe1p",
                "CaSe1q",
                "CaSe1r",
                "CaSe1t",
                "CaSe1u",
                "CaSe1w",
                "CaSe1y",
                "CaSe2e",
                "CaSe2i",
                "CaSe2o",
                "CaSe2p",
                "CaSe2q",
                "CaSe2r",
                "CaSe2t",
                "CaSe2u",
                "CaSe2w",
                "CaSe2y",
                "CaSe3e",
                "CaSe3i",
                "CaSe3o",
                "CaSe3p",
                "CaSe3q",
                "CaSe3r",
                "CaSe3t",
                "CaSe3u",
                "CaSe3w",
                "CaSe3y",
            },
        )
        _runcase(
            desc="CaSe -> replace `cAs` with `Fac`",
            simple=True,
            regex=r"CaSe(\d[qwertyuiop])",
            renamer=Renamer(case_insensitive=True),
            substring_from="cAs",
            substring_to="Fac",
            except_regex=r"e$",
            files={
                "CaSe1e",
                "Face1i",
                "Face1o",
                "Face1p",
                "Face1q",
                "Face1r",
                "Face1t",
                "Face1u",
                "Face1w",
                "Face1y",
                "CaSe2e",
                "Face2i",
                "Face2o",
                "Face2p",
                "Face2q",
                "Face2r",
                "Face2t",
                "Face2u",
                "Face2w",
                "Face2y",
                "CaSe3e",
                "Face3i",
                "Face3o",
                "Face3p",
                "Face3q",
                "Face3r",
                "Face3t",
                "Face3u",
                "Face3w",
                "Face3y",
            },
        )

    which_fs = _runtest(test_fs_case, show_dir=True)
    tests = {
        CASE_SENSITIVE: _case_sensitive_tests,
        CASE_PRESERVING: _case_preserving_tests,
    }
    if which_fs not in tests:  # pragma: no cover
        sys.exit(which_fs)
    tests[which_fs]()
    if failures == 0:  # pragma: no cover
        print("All tests OK.")
    return StatusCode(failures)


if __name__ == "__main__":
    run()
