#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import json
import pathlib
import sh
import typing

import timewarp.error
import timewarp.namespace


class Block(object):
    """Block device."""

    def __init__(self) -> None:
        self.uuid = None


class FileSystem(Block):
    """File system block device."""

    def __init__(self, mount_point: str) -> None:
        super().__init__()

        # Get the mount target, file system type, UUID and mount options for
        # the file system.
        try:
            block = json.loads(
                str(sh.findmnt(
                    mount_point, "-J", "-o", "TARGET,FSTYPE,UUID,OPTIONS")),
                object_hook=lambda kwargs: timewarp.namespace.Namespace(
                    **kwargs))
        except sh.CommandNotFound:
            raise timewarp.error.InitializationError(
                "findmnt: Command not found")
        except sh.ErrorReturnCode:
            raise timewarp.error.InitializationError(
                f"Invalid mount point {mount_point}")

        self.subvol = None

        for option in block.filesystems[0].options.split(","):
            if option.startswith("subvol="):
                self.subvol = pathlib.Path(option.split("=")[-1])
                break

        self.file_system_type = block.filesystems[0].fstype
        self.uuid = block.filesystems[0].uuid


class Partition(Block):
    """Partition block device."""

    def __init__(self, mount_point: str) -> None:
        super().__init__()

        # In case Btrfs subvolumes are being used, lsblk might not be able to
        # properly determine the mount points.  To work around this, we first
        # determine the file system UUID and use it to find the correct
        # partition.
        file_system = FileSystem(mount_point)

        # Get the device name, path to the device node, file system UUID,
        # partition table type and device type for all block devices.
        try:
            root = json.loads(
                str(sh.lsblk("-J", "-o", "NAME,PATH,UUID,PTTYPE,TYPE")),
                object_hook=lambda kwargs: timewarp.namespace.Namespace(
                    **kwargs))
        except sh.CommandNotFound:
            raise timewarp.error.InitializationError(
                "lsblk: Command not found")

        # Try to find the partition.
        partition, found = self._find_partition(root, file_system.uuid)

        if found:
            self.path = partition.path
            self.uuid = partition.uuid
            self.partition_table_type = partition.pttype
        else:
            self.path = None
            self.uuid = None
            self.partition_table_type = None

    def _find_partition(
            self, root: timewarp.namespace.Namespace, file_system_uuid: str,
            partition: timewarp.namespace.Namespace = None,
            found: bool = False) -> typing.Tuple[typing.Optional[str], bool]:
        if not found:
            if "type" in root and "part" == root.type:
                # The current block device is a partition so we save it.
                partition = root

            if "uuid" in root and file_system_uuid == root.uuid:
                # The current UUID matches the file system UUID, this means we
                # found the right partition.
                found = True

            # Traverse sub-elements.
            if "blockdevices" in root:
                for block_device in root.blockdevices:
                    partition, found = self._find_partition(
                        block_device, file_system_uuid, partition, found)
            elif "children" in root:
                for child in root.children:
                    partition, found = self._find_partition(
                        child, file_system_uuid, partition, found)

        return partition, found
