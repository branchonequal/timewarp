#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import pathlib
import re
import typing

import timewarp.error
import timewarp.service.package


class Dpkg(timewarp.service.package.Database):
    """Debian Package Manager database."""

    def __init__(self, root: pathlib.Path) -> None:
        super().__init__(root)
        self._path = root / "var" / "lib" / "dpkg"

        if not self._path.exists():
            raise timewarp.error.InitializationError(
                f"Local dpkg package database {self._path} does not exist")

    def get_packages_by_name(
            self, name: str) -> \
            typing.Sequence[timewarp.service.package.Package]:
        """
        Returns all packages identified by name.  Raises PackageNotFoundError
        if no package with the specified name could be found.

        Keyword arguments:
        name -- the package name
        """
        result = []

        with open(self._path / "status", "r") as f:
            buffer = f.read()

        for m in re.finditer(
                fr"Package: (?P<name>{name}(-\d[\w\-\.]+)?)\s+"
                fr"Status: (?P<status>[\w ]+)\s+"
                fr".*?"
                fr"Version: (?P<version>[\w\-\.]+)\s+", buffer, re.DOTALL):
            if "installed" in m.group("status").split(" "):
                result.append(timewarp.service.package.Package(
                    m.group("name"), m.group("version")))

        if result:
            return result

        raise timewarp.error.PackageNotFoundError
