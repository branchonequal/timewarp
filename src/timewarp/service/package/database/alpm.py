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


class ALPM(timewarp.service.package.Database):
    """Arch Linux Package Manager database."""

    def __init__(self, root: pathlib.Path) -> None:
        super().__init__(root)
        self._path = root / "var" / "lib" / "pacman" / "local"

        if not self._path.exists():
            raise timewarp.error.InitializationError(
                f"Local ALPM package database {self._path} does not exist")

    def get_packages_by_name(
            self, name: str) -> \
            typing.Sequence[timewarp.service.package.Package]:
        """
        Returns all packages identified by name.  Raises PackageNotFoundError
        if no package with the specified name could be found.  Additionally
        raises InvalidPackageInformationError if the package data could not be
        processed properly.

        Keyword arguments:
        name -- the package name
        """
        result = []

        for desc in self._path.glob(f"{name}-*/desc"):
            with open(desc, "r") as f:
                buffer = f.read()

            if re.search(fr"%NAME%\s+{name}\s+", buffer):
                m = re.search(r"%VERSION%\s+(?P<version>.*)\s+", buffer)

                if m:
                    result.append(timewarp.service.package.Package(
                        name, m.group("version")))
                else:
                    raise timewarp.error.InvalidPackageInformationError

        if result:
            return result

        raise timewarp.error.PackageNotFoundError
