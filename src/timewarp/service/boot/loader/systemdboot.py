#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import pathlib

import timewarp.error
import timewarp.service.boot


class SystemDBoot(timewarp.service.boot.Loader):
    """systemd-boot boot loader."""

    def __init__(
            self, mount_point: pathlib.Path,
            boot_on_root: bool = False) -> None:
        super().__init__(mount_point)
        self._path = mount_point / "loader" / "entries"

        if not self._path.exists():
            raise timewarp.error.InitializationError(
                f"Directory {self._path} does not exist")

    def add_entry(
            self, number: int, entry: timewarp.service.boot.Entry) -> None:
        """
        Adds a new systemd-boot boot loader entry.

        Keyword arguments:
        number -- the snapshot number
        entry  -- the entry to add
        """
        buffer = []
        width = len(max(vars(entry).keys(), key=len))

        for name, value in vars(entry).items():
            if not value:
                continue
            elif "architecture" == name:
                buffer.append(f"{name:<{width}} {value.lower()}")
            elif "options" == name:
                options = []

                for option in value:
                    if isinstance(option, dict):
                        options += (
                            [f"{name_}={value_}"
                                for name_, value_ in option.items()])
                    else:
                        options.append(option)

                buffer.append(f"{name:<{width}} {' '.join(options)}")
            elif isinstance(value, list):
                buffer += [f"{name:<{width}} {value_}" for value_ in value]
            else:
                buffer.append(f"{name.replace('_', '-'):<{width}} {value}")

        # Generated boot loader entries start with zz and the snapshot number,
        # counting down from 0xFFFFFFFF.  This way, systemd-boot will put the
        # standard entries on top, followed by the generated entries in reverse
        # chronological order.
        components = ["zz", f"{0xFFFFFFFF - number:08x}"]

        if entry.machine_id:
            components.append(entry.machine_id)

        if entry.version:
            components.append(entry.version)

        if entry.architecture:
            components.append(entry.architecture)

        filename = self._path / f"{'-'.join(components)}.conf"

        with open(filename, "w") as f:
            f.write("\n".join(buffer))

    def remove_entry(self, number: int) -> None:
        """
        Removes a systemd-boot boot loader entry.

        Keyword arguments:
        number -- the snapshot number
        """
        for file in self._path.glob(f"zz-{0xFFFFFFFF - number:08x}*.conf"):
            file.unlink()
