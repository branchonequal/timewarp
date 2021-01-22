#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import pathlib
import re

import timewarp.error
import timewarp.service.block
import timewarp.service.boot


class GRUB(timewarp.service.boot.Loader):
    """GRUB boot loader."""

    def __init__(
            self, mount_point: pathlib.Path,
            boot_on_root: bool = False) -> None:
        super().__init__(mount_point)
        self._path = mount_point / "grub"

        if not self._path.exists():
            raise timewarp.error.InitializationError(
                f"Directory {self._path} does not exist")

        # GRUB needs information about the boot partition device in order to be
        # able to find the kernel and initrd images.  The same information also
        # needs to be passed to the "search" command.
        boot_partition = timewarp.service.block.Partition(
            mount_point if not boot_on_root else "/")
        name = boot_partition.path.split("/")[-1]

        # ATA or SATA/SCSI drive.
        m = re.match(
            r"(?P<controller_type>[hs])d(?P<drive_number>[a-z])"
            r"(?P<partition_number>\d+)", name)

        if m:
            baremetal_drive = \
                "ata" if "h" == m.group("controller_type") else "ahci"
            drive_number = ord(m.group("drive_number")) - 0x61
            partition_number = int(m.group("partition_number"))
        else:
            # NVMe drive.
            m = re.match(
                r"nvme\d+n(?P<drive_number>\d+)p(?P<partition_number>\d+)",
                name)

            if m:
                baremetal_drive = "ahci"
                drive_number = int(m.group("drive_number")) - 1
                partition_number = int(m.group("partition_number"))
            else:
                raise timewarp.error.InitializationError(
                    f"Unable to determine type of device "
                    f"{boot_partition.path}")

        if "gpt" == boot_partition.partition_table_type:
            partition = f"gpt{partition_number}"
        elif "dos" == boot_partition.partition_table_type:
            partition = f"msdos{partition_number}"
        else:
            raise timewarp.error.InitializationError(
                f"Unrecognized partition table type "
                f"{boot_partition.partition_table_type}")

        self._root_file_system = timewarp.service.block.FileSystem("/")

        if not boot_on_root:
            self._boot_file_system = timewarp.service.block.FileSystem(
                mount_point)
        else:
            self._boot_file_system = self._root_file_system

        self._root = f"hd{drive_number},{partition}"
        self._baremetal_root = f"{baremetal_drive}{drive_number},{partition}"
        self._modules = ["gzio"]

        if "gpt" == boot_partition.partition_table_type:
            self._modules.append("part_gpt")

        if "btrfs" == self._boot_file_system.file_system_type:
            self._modules.append("btrfs")
        elif "vfat" == self._boot_file_system.file_system_type:
            self._modules.append("fat")

    def add_entry(
            self, number: int, entry: timewarp.service.boot.Entry) -> None:
        """
        Adds a new GRUB boot loader entry.

        Keyword arguments:
        number -- the snapshot number
        entry  -- the entry to add
        """
        lf = "\n"
        options = []
        buffer = ""

        try:
            with open(self._path / "grub-timewarp.cfg", "r") as f:
                m = re.search("(?P<entries>###.*###)", f.read(), re.DOTALL)

                if m:
                    buffer = m.group("entries")
        except FileNotFoundError:
            pass

        if entry.options is not None:
            for option in entry.options:
                if isinstance(option, dict):
                    options += (
                        [f"{name_}={value_}"
                            for name_, value_ in option.items()])
                else:
                    options.append(option)

        # I am very sorry for this mess but GRUB configuration files clash
        # badly with Pythons 80 column limit.
        buffer = f"""    ### BEGIN Boot loader entry for snapshot {number} ###
    menuentry '{entry.title}' --class snapshots --class gnu-linux --class gnu \
--class os $menuentry_id_option \
'gnulinux-snapshots-{self._root_file_system.uuid}' {{
        load_video
        set gfxpaylod=keep
{f"{lf}".join(map(lambda module: f"        insmod {module}", self._modules))}
        set root='{self._root}'
        if [ x$feature_platform_search_hint = xy ]; then
          search --no-floppy --fs-uuid --set=root --hint-bios={self._root} \
--hint-efi={self._root} --hint-baremetal={self._baremetal_root} \
{self._boot_file_system.uuid}
        else
          search --no-floppy --fs-uuid --set=root {self._boot_file_system.uuid}
        fi
        echo 'Loading Linux linux ...'
        linux {entry.linux} {" ".join(options)}
        echo 'Loading initial ramdisk ...'
        initrd {" ".join(entry.initrd)}
    }}
    ### END Boot loader entry for snapshot {number} ###

    """ + buffer

        with open(self._path / "grub-timewarp.cfg", "w") as f:
            f.write(f"""submenu 'Snapshots' {{
    {buffer.strip()}
}}""")

    def remove_entry(self, number: int) -> None:
        """
        Removes a GRUB boot loader entry.

        Keyword arguments:
        number -- the snapshot number
        """
        file = self._path / "grub-timewarp.cfg"
        buffer = ""

        try:
            with open(file, "r") as f:
                m = re.search("(?P<entries>###.*###)", f.read(), re.DOTALL)

                if m:
                    buffer = m.group("entries")
        except FileNotFoundError:
            return

        buffer = re.sub(
            f"### BEGIN Boot loader entry for snapshot {number} ###.*"
            f"### END Boot loader entry for snapshot {number} ###",
            "", buffer, flags=re.DOTALL)

        if re.search("### BEGIN", buffer):
            with open(file, "w") as f:
                f.write(f"""submenu 'Snapshots' {{
    {buffer.strip()}
}}""")
        else:
            file.unlink()
