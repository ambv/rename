# rename

[![PyPI - Version](https://img.shields.io/pypi/v/rename.svg)](https://pypi.org/project/rename)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/rename.svg)](https://pypi.org/project/rename)
[![code style - black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![types - Mypy](https://img.shields.io/badge/types-Mypy-blue.svg)](https://github.com/python/mypy)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)

-----

Renames files using regular expression matching. This enables elegant handling
of multiple renames using a single command.

**Table of Contents**

- [Installation](#installation)
- [Usage](#usage)
- [Options](#options)
- [License](#big-friendly-disclaimer)

## Installation

The script is a single file that will work with any Python 3.7+.  If you
prefer, install with:

``console
pip install rename
``

There used to be a version compatible with Python 2.4 - 2.7.  To use that
one, install `rename==1.2`.

## Usage

Basic syntax:

```console
rename [-I] [-l] [-q] [-t] [-u] [-v "except_regex"] "regex" "target"
```

```console
rename -s [-I] [-l] [-q] [-t] [-u] [-v "except_regex"] "substring_from" "substring_to" "regex"
```

```console
rename --selftest [directory]
```

## Options

### `regex`
Regular expression that matches source files which are to be renamed. Examples:

```
"(\w+).caf"
"IMG(\d\d\d\d\).[Jj][Pp][Ee]?[Gg]"
"([0-9]{2})-([0-9]{2})-([12][0-9]{3}).log"
```

The regular expression is **global** by default (e.g. writing `"[0-9]"` means
`"^[0-9]$"`). This is to avoid accidental partial catches. If you want to match
all files that start or end with a specific expression, add `.*` to the
expression, e.g. `".*\.mp3"` will match all files that end with `.mp3`.  While
that may seem a bit redundant, it's on par with ["explicit is better than
inplicit"](http://www.python.org/dev/peps/pep-0020/). See also: `-I`.

**Note:** the regex is case-sensitive, also on case-preserving filesystems. If
you wish to change that, use the `-I` option.

### `target`
Name of the target file with references to regular expression groups caught in
the source matches. References to groups are formed by a backslash character
followed by he group number. Groups are indexed from 1. The group number can be
contained within parentheses to disambiguate a reference followed by digits.
Examples:

```
"\1.aiff"
"\(1)1337.zip"
"\3-\1-\2.log"
```

Automatic numbering can be introduced using a special `\(index)` reference.
For example:

```console
rename "IMG.*\.JPG" "Judy's Birthday \(index).jpg"
```

By default indexing starts with 1, increments with 1 and pads numbers with
enough leading zeroes so that each filename uses the same amount of digits.
This can be changed with the `--index-first`, `--index-step`,
`--index-digits` and `--index-pad-with` options.

### `substring_from`, `substring_to`

When using the "simple" mode (`-s`), these arguments provide the traditional
search/replace pattern:

 * `substring_from` is a simple (raw) substring that should be found within
   the filename

 * `substring_to` is the replacement string

Both of these strings are raw, e.g. they don't allow for any wildcards, regular
expressions and whatnot. This is more-less compatible with behavior of the
existing `rename` tool from the `util-linux-ng` package. One obvious
difference is that the file mask doesn't use wildcards but regular expressions.

Example (translating underscores to spaces):

```console
rename -s "_"  " "  ".*\.txt" 
```

**Note:** `substring_from` is case-sensitive, also on case-preserving
filesystems.  If you wish to change that, use the `-I` option.
`substring_to` is always case-sensitive.

### `-I`, or `--case-insensitive`
When used, regexes work in a case-insensitive manner, e.g. `"lib"` will behave
like `"[Ll][Ii][Bb]"`. Group references still hold the original case.

### `-l`, or `--lower`
When used, renamed filenames are transformed to lower-case. This does not affect
the source regex used (i.e. it still matches in a case-sensitive manner, unless
`-I` is used). See also: `-U`.

### `-q`, or `--quiet`
When used, no error output is given. The status of invocation should be
determined via the return code.

### `-s`, or `--simple`

Invokes the "simple" mode. See: `substring_from`, `substring_to`.

### `-t`, or `--test`
When used, the script will only fake renaming and verbosely state what it would
do. Use this if you're unsure of the effects your expression may cause.  

### `-U`, or `--upper`
When used, renamed filenames are transformed to upper-case. This does not affect
the source regex used (i.e. it still matches in a case-sensitive manner, unless
`-I` is used). See also: `-l`.

### `-v "except_regex"`, or `--except "except_regex"`
When used, any filename matched by the original source regex will be also
matched against the `except_regex`. In case there is a match, the filename is
skipped. In other words, filenames that match `except_regex` will **not** be
renamed.

The regular expression is **local** (e.g. writing `"[0-3]"` means "number
0-3 anywhere in the filename). This is to make the tool err on the side of
caution by protecting from renaming too many files by accident when the user
forgets to add dot-asterisk to `-v`. If you want to only match whole
filenames, use the canonical global form (e.g. `"^filename$"`).

Why `-v`? Because `grep -v`.

See also: `-I`.

### `--index-first`
When using the special `\(index)` reference, this option specifies what number
will the first index be. Default: `--index-first=1`.

### `--index-step`
When using the special `\(index)` reference, this option specifies what number
will be added with each step to the first value. The specified number can be
negative. Default: `--index-step=1`.

### `--index-digits`
When using the special `\(index)` reference, this option specifies how many
digits will be used in each reference. If a number has fewer digits, they will
be prefixed by leading zeroes (or another character, see: `--index-pad-with`).
A special value of `auto` can be used to automatically pad enough digits so
that each filename has the same amount of them used. This is useful for ensuring
your files will be sorted correctly even by dumb algorithms. Default:
`--index-digits=auto`.

### `--index-pad-with`
When using the special `\(index)` reference, this option specifies what
character will be used for padding. Default: `--index-pad-with=0`. 

### `--selftest`
Runs internal unit tests of all functionality. Does actual renaming of
a generated set of files in the specified directory. If no directory is passed,
uses the temporary directory. Each test generates its own set of files.

You can use this to test the tool on a new machine and/or filesystem to
ensure the results are sane.

## Security
1. The script will not let multiple files be renamed to a single name.

2. The script will not let existing files to be overwritten.

3. Both checks above are made for all matches before any renaming is performed.

4. The script correctly preserves extended attributes and ACLs.

## Other remarks
1. Regular expressions supported by the script must conform to the syntax
   handled by Python's [`re` module](http://docs.python.org/library/re.html).

2. Actual renaming of a single file is done by the
   [`os.rename()`](http://docs.python.org/library/os.html#os.rename) function
   from Python's standard library. No additional atomicity is ensured, e.g. if a
   single rename fails halfway through, the filesystem is left in a state of
   partially complete renaming.

3. Due to differences in behavior of different shells, the recommended form of
   execution is to put both arguments in quotation marks.

This project might look new on Github but it's in fact a revived script
from 2011, moved over to Python 3, Mypy, Hatch, pytest, all that good
stuff. Some of the code might reflect my 2011 state of mind.

## Possible future enhancements
1. `-p` option to create intermediate directories for the target. One tiny
   problem is maintaining atomicity of the whole transaction.

2. `-r` option to make the source match recursive. Tricky to get right
   I guess, e.g. where to rename? Existing directory structure or new one?. Let
   the user decide? What's the default? Etc. etc.

3. Interactive mode. Things to be thought over: should the question appear
   before the transaction begins, before each step, or both? Should that be one
   option?

## BIG FRIENDLY DISCLAIMER
This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE. See the GNU General Public License for more details.

**DON'T PANIC**. This code has been successfully used by its author and
contains tests with 100% coverage. However, be especially wary under these
conditions:

1. Renaming between filesystems.

2. Renaming under non case-preserving filesystems.

3. Renaming within very long paths.

4. Renaming volatile state (e.g. rotating logs).

And if you do lose any data, it's your fault. Have a nice day!

## Authors
Script glued together by [Łukasz Langa](mailto:lukasz@langa.pl).

