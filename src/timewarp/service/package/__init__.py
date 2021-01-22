#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import pathlib
import typing


class Package(object):
    """Package."""

    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version


class Database(object):
    """Package database."""

    def __init__(self, root: pathlib.Path) -> None:
        if type(self) is Database:
            raise NotImplementedError

    def get_packages_by_name(self, name: str) -> typing.Sequence[Package]:
        """
        Returns all packages identified by name.  Raises PackageNotFoundError
        if no package with the specified name could be found.

        Keyword arguments:
        name -- the package name
        """
        raise NotImplementedError
