#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import pathlib
import typing


class Entry(object):
    """Boot loader entry."""

    def __init__(
            self, linux: str, title: str = None, version: str = None,
            machine_id: str = None, initrd: typing.Iterable[str] = None,
            options: typing.Iterable[str] = None,
            architecture: str = None) -> None:
        self.title = title
        self.version = version
        self.machine_id = machine_id
        self.linux = linux
        self.initrd = initrd
        self.options = options
        self.architecture = architecture


class Loader(object):
    """Boot loader."""

    def __init__(
            self, mount_point: pathlib.Path,
            boot_on_root: bool = False) -> None:
        if type(self) is Loader:
            raise NotImplementedError

    def add_entry(self, number: int, entry: Entry) -> None:
        """
        Adds a new boot loader entry.

        Keyword arguments:
        number -- the snapshot number
        entry  -- the entry to add
        """
        raise NotImplementedError

    def remove_entry(self, number: int) -> None:
        """
        Removes a boot loader entry.

        Keyword arguments:
        number -- the snapshot number
        """
        raise NotImplementedError
