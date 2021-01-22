<h1 align="center">Time Warp</h1>
<p align="center">Fully automated Snapper snapshot and boot environment creation.</p>

## Features
* Creates Snapper snapshots via snapperd.
* Copies the kernel and required initrd images.
* Creates boot environments from the snapshots.
* Creates the corresponding boot loader entries.
* Keeps track of deleted snapshots and automatically cleans up boot loader entries, boot environments and kernel and initrd images.
* Has extensible boot loader and package database module support.
  * Currently supported boot loaders: GRUB, systemd-boot.
  * Currently supported database formats: ALPM, dpkg.

## Limitations
* As boot environments are implemented as Btrfs subvolumes, the root file system has to be Btrfs.

## Installation
### Arch Linux Package
An Arch Linux `PKGBUILD` is available [here](https://github.com/branchonequal/timewarp-arch-pkg).

### Manual
Required Python modules:
* [argh](https://pypi.org/project/argh/),
* [jsonschema](https://pypi.org/project/jsonschema/),
* [pydbus](https://pypi.org/project/pydbus/),
* [PyGObject](https://pypi.org/project/PyGObject/),
* [sh](https://pypi.org/project/sh/).

1. Install Time Warp with `pip`.
1. Copy `com.branchonequal.TimeWarp.conf` to your D-Bus system bus configuration directory.
   * **Arch Linux/Debian:** The configuration files are located in `/usr/share/dbus-1/system.d`.
1. Copy `timewarp.service` to your systemd system unit directory.
   * **Arch Linux/Debian:** The unit files are located in `/usr/lib/systemd/system`.
1. Optionally install the package database transaction hooks.
   * **Arch Linux:** The transaction hooks are located in `/etc/pacman.d/hooks`.
   * **Debian:** The transaction hooks are located in `/etc/apt/apt.conf.d`.
1. When using GRUB: Copy `42_timewarp` to `/etc/grub.d`.

### Post-Installation Actions
1. Create `/etc/xdg/timewarp/timewarp.conf` using the provided example.
1. Enable the Time Warp service:
```sh
systemctl enable timewarp
systemctl start timewarp
```

## Configuration
### Options
* `boot` &mdash; Boot configuration.
  * `boot_on_root` &mdash; Set to `true` if `/boot` is located on the root file system. Default: `false`.
  * `entry` &mdash; Boot loader entry configuration, complying with the systemd boot loader specification.
    * `title` &mdash; Contains an optional title.
    * `version` &mdash; Contains an optional version.
    * `machine_id` &mdash; Contains an optional unique machine ID.
    * `options` &mdash; Contains an optional list of kernel options. Might contain strings and _name: value_ pairs in any order.
    * `architecture` &mdash; Contains an optional EFI architecture identifier.
    * `linux` &mdash; Contains the kernel image file name.
    * `initrd` &mdash; Contains an optional list of initrd image file names.
  * `loader` &mdash; Contains the boot loader module name. Supported values: `grub`, `systemdboot`.
  * `mount_point` &mdash; Contains the boot partition mount point. Default: `/boot`.
* `bootenv` &mdash; Contains the path to the boot environment directory. Default: `/.bootenv`.
* `machine_id` &mdash; Contains the path to the `machine-id` file. Default: `/etc/machine-id`.
* `package` &mdash; Package configuration.
  * `database` &mdash; Contains the package database module name. Supported values: `alpm`, `dpkg`.
  * `important` &mdash; Contains a list of package names. The command line program reads the list of packages to be updated from `stdin`. If one of the packages is contained in the list of important packages, `important=yes` will be set for the snapshot. `important=yes` will be set for post-snapshots automatically if it was set for the corresponding pre-snapshot.
  * `linux` &mdash; Contains the kernel package name.
* `snapper` &mdash; Snapper configuration.
  * `cleanup_algorithm` &mdash; Contains the snapshot cleanup algorithm.
  * `description` &mdash; Contains the snapshot description.
  * `name` &mdash; Contains the root configuration name. Default: `root`.
* `snapshots` &mdash; Contains the path to the snapshot directory. Default: `/.snapshots`.

### Replacement Fields
Configuration values might contain replacement fields. The following replacement fields are supported:

#### EFI Architecture Identifier
* `{architecture}` &mdash; Contains the EFI architecture identifier for the identified machine type.

#### Kernel Package
* `{linux.name}` &mdash; Contains the kernel package name.
* `{linux.version}` &mdash; Contains the kernel package version.

#### Unique Machine ID
* `{machine_id}` &mdash; Contains the unique machine ID, read from local machine ID configuration file.

#### Root File System
* `{root_file_system.file_system_type}` &mdash; Contains the root file system type.
* `{root_file_system.subvol}` &mdash; Contains the root file system subvolume name.
* `{root_file_system.uuid}` &mdash; Contains the root file system UUID as reported by `findmnt`.

#### Root Partition
* `{root_partition.partition_table_type}` &mdash; Contains the root partition partition table type.
* `{root_partition.path}` &mdash; Contains the root partition path.
* `{root_partition.uuid}` &mdash; Contains the root partition UUID as reported by `lsblk`.

#### Snapshot
* `{snapshot.number}` &mdash; Contains the snapshot number.
* `{snapshot.type}` &mdash; Contains the snapshot type (`pre`, `post` or `single`).
* `{snapshot.pre_number}` &mdash; Contains the pre-snapshot number.
* `{snapshot.date}` &mdash; Contains the snapshot date and time.
* `{snapshot.user}` &mdash; Contains the snapshot user ID.
* `{snapshot.description}` &mdash; Contains the snapshot description.
* `{snapshot.cleanup_algorithm}` &mdash; Contains the snapshot cleanup algorithm.
* `{snapshot.userdata}` &mdash; Contains the snapshot user data.

## Usage
### Snapshot Creation
If you installed the package database transaction hooks, Time Warp will create a snapshot before and after each transaction.

Snapshots can also be created manually by running
```sh
timewarp create -t {pre,post,single}
```

To temporarily disable Time Warp when using the package manager, set the `DISABLE_TIMEWARP` environment variable to an arbitrary value before executing the command.

### Snapshot Deletion
Snapshots can be deleted via `snapper delete <Snapshot number>`. Time Warp will automatically remove the corresponding boot loader entry and delete the boot environment and unused kernel and initrd images. If the boot environment to be deleted is in use it will be left untouched and deleted on the next boot.
