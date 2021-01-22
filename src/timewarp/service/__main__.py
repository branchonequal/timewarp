#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import enum
import functools
from gi.repository import Gio, GLib
import importlib
import pathlib
import platform
import pydbus
import sh
import shutil
import signal
import sys
import syslog
import typing

import timewarp.configuration
import timewarp.error
import timewarp.service.block
import timewarp.service.snapper


class Architecture(enum.Enum):
    """EFI architecture identifier."""

    aarch64 = "AA64"
    aarch64_be = "AA64"
    arm = "ARM"
    ia32 = "IA32"
    ia64 = "IA64"
    x86_64 = "X64"


class Service(object):
    """
    <node>
        <interface name="com.branchonequal.TimeWarp">
            <method name="CreatePreSnapshot">
                <arg type="b" name="important" direction="in"/>
                <arg type="u" name="number" direction="out"/>
            </method>
            <method name="CreatePostSnapshot">
                <arg type="u" name="number" direction="out"/>
            </method>
            <method name="CreateSingleSnapshot">
                <arg type="b" name="important" direction="in"/>
                <arg type="u" name="number" direction="out"/>
            </method>
        </interface>
    </node>
    """

    """Time Warp service."""

    def __init__(self) -> None:
        system_bus = pydbus.SystemBus()

        # Check if timewarpd is already running.
        try:
            system_bus.get("com.branchonequal.TimeWarp")
            running = True
        except GLib.Error:
            running = False

        if running:
            raise timewarp.error.InitializationError(
                "timewarpd is already running")

        self._in_init = True
        self._userdata = {}

        # Set up a signal handler to cleanly quit the main event loop on
        # Ctrl+C and SIGTERM.
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Set up the main event loop.
        self._loop = GLib.MainLoop()

        # Load the configuration.  Raises InitializationError if the
        # configuration file could not be found or the configuration is
        # invalid.
        self._configuration = timewarp.configuration.Configuration()

        self._bootenvs = pathlib.Path(self._configuration.bootenv)
        self._linux = self._configuration.package.linux
        self._mount_point = pathlib.Path(self._configuration.boot.mount_point)
        self._snapshots = pathlib.Path(self._configuration.snapshots)

        boot_on_root = self._configuration.boot.boot_on_root \
            if "boot_on_root" in self._configuration.boot else False
        database = self._configuration.package.database
        loader = self._configuration.boot.loader
        machine_id = self._configuration.machine_id
        snapper = self._configuration.snapper

        # Import the boot loader module.
        try:
            importlib.import_module(f"timewarp.service.boot.loader.{loader}")
        except ModuleNotFoundError as e:
            raise timewarp.error.InitializationError(
                f"Boot loader module {loader} not found")

        # Import the package database module.
        try:
            importlib.import_module(
                f"timewarp.service.package.database.{database}")
        except ModuleNotFoundError as e:
            raise timewarp.error.InitializationError(
                f"Package database module {database} not found")

        # Check if the /boot mount point exists and the partition is mounted.
        if not self._mount_point.exists():
            raise timewarp.error.InitializationError(
                f"Boot partition mount point {self._mount_point} "
                f"does not exist")

        if not list(self._mount_point.glob("*")):
            raise timewarp.error.InitializationError(
                "Boot partition is not mounted")

        # Initialize the boot loader with the /boot mount point.  Raises
        # InitializationError if a boot loader-specific check has failed.
        self._loader = timewarp.service.boot.Loader.__subclasses__()[0](
            self._mount_point, boot_on_root)

        # As we need to be able to access the package databases of boot
        # environments we store the package database class for later use and
        # also initialize the root package database.  Raises
        # InitializationError if the local package database could not be found.
        self._database = timewarp.service.package.Database.__subclasses__()[0]
        self._root_database = self._database(pathlib.Path("/"))

        # Check if we can query the kernel package.
        try:
            linux = self._root_database.get_packages_by_name(self._linux)[-1]
        except timewarp.error.PackageNotFoundError:
            raise timewarp.error.InitializationError(
                f"Kernel package {self._linux} not found")
        except timewarp.error.InvalidPackageInformationError:
            raise timewarp.error.InitializationError(
                "Failed to query database package: "
                "Invalid package information")

        # Check if the boot environment and snapshot directories exist.
        if not self._bootenvs.exists():
            raise timewarp.error.InitializationError(
                f"Boot environment directory {self._bootenvs} does not exist")

        if not self._snapshots.exists():
            raise timewarp.error.InitializationError(
                f"Snapshot directory {self._snapshots} does not exist")

        # Initialize the GIO file monitor for monitoring the snapshot
        # directory.
        self._monitor = Gio.file_new_for_path(
            bytes(self._snapshots)).monitor(Gio.FileMonitorFlags.NONE, None)
        self._monitor.connect("changed", self._monitor_handler)

        # Read the local machine ID.
        try:
            with open(machine_id, "r") as f:
                machine_id_ = f.read().strip()
        except FileNotFoundError:
            raise timewarp.error.InitializationError(
                f"Local machine ID configuration file {machine_id} not found")

        # This is the default mapping for substituting replacement fields in
        # boot entry format strings.
        self._default_mapping = {
            "architecture": Architecture[platform.machine()].value,
            "machine_id": machine_id_,
            "root_file_system": timewarp.service.block.FileSystem("/"),
            "root_partition": timewarp.service.block.Partition("/")
        }

        # Check for invalid replacement fields in the boot entry configuration.
        # For this we are setting up a dummy snapshot.
        mapping = {
            **self._default_mapping,
            "linux": linux,
            "snapshot": timewarp.service.snapper.Snapshot(
                0, 0, 0, 0, 0, "", "", {})
        }

        try:
            self._configuration.format(mapping, self._configuration.boot.entry)
        except (AttributeError, KeyError) as e:
            raise timewarp.error.InitializationError(
                f"Invalid replacement field in boot entry configuration: {e}")

        # Initialize Snapper.  Raises InitializationError if snapperd is not
        # running.
        self._snapper = timewarp.service.snapper.Snapper(
            snapper.name, snapper.cleanup_algorithm)

        # Clean up orphaned boot environments.
        bootenvs = set([file.name for file in self._bootenvs.glob("*")])
        snapshots = set([file.name for file in self._snapshots.glob("*")])

        for bootenv in bootenvs - snapshots:
            try:
                self._clean_up(int(bootenv), True)
            except ValueError:
                pass

        # Publish the service on the D-Bus system bus.
        try:
            system_bus.publish("com.branchonequal.TimeWarp", self)
        except GLib.Error as e:
            raise timewarp.error.InitializationError(
                f"Connection to the D-Bus system bus failed: "
                f"{timewarp.error.DBusError(e.code)}")

        # Set syslog logging options.
        syslog.openlog("timewarpd")
        self._in_init = False

    def CreatePreSnapshot(self, important: bool) -> int:
        """Creates a new pre-snapshot, returning the snapshot number."""
        self._userdata = {"important": "yes"} if important else {}
        return self._create_snapshot(timewarp.service.snapper.SnapshotType.PRE)

    def CreatePostSnapshot(self) -> int:
        """Creates a new post-snapshot, returning the snapshot number."""
        return self._create_snapshot(
            timewarp.service.snapper.SnapshotType.POST)

    def CreateSingleSnapshot(self, important: bool) -> int:
        """Creates a new single snapshot, returning the snapshot number."""
        self._userdata = {"important": "yes"} if important else {}
        return self._create_snapshot(
            timewarp.service.snapper.SnapshotType.SINGLE)

    def start(self) -> None:
        """Starts the main event loop."""
        self._loop.run()

    def _clean_up_error_handler(
            function: typing.Callable[..., None]) -> \
            typing.Callable[..., None]:
        @functools.wraps(function)
        def decorator(
                self, *args: typing.Iterable[typing.Any],
                **kwargs: typing.Iterable[typing.Any]) -> None:
            bootenv = self._bootenvs / str(args[0])

            try:
                function(self, *args, **kwargs)
            except timewarp.error.InitializationError as e:
                if not self._in_init:
                    syslog.syslog(
                        syslog.LOG_ERR, f"Failed to initialize package "
                        f"database of boot environment {bootenv}: {e.message}")
            except timewarp.error.InvalidPackageInformationError:
                if not self._in_init:
                    syslog.syslog(
                        syslog.LOG_ERR, f"Failed to query package database of "
                        f"boot environment {bootenv}: Package information for "
                        f"kernel package {self._linux} is invalid")
            except timewarp.error.PackageNotFoundError:
                if not self._in_init:
                    syslog.syslog(
                        syslog.LOG_ERR, f"Failed to query package database of "
                        f"boot environment {bootenv}: Kernel package "
                        f"{self._linux} not found")
            except timewarp.error.SubvolumeError as e:
                if not self._in_init:
                    syslog.syslog(syslog.LOG_ERR, e.message)
            except Exception as e:
                syslog.syslog(syslog.LOG_ERR, f"Unexpected error: {e}")

        return decorator

    @_clean_up_error_handler
    def _clean_up(self, number: int, quiet: bool = False) -> None:
        bootenv = self._bootenvs / str(number)
        file_system = timewarp.service.block.FileSystem("/")

        # Remove the boot loader entry.
        self._loader.remove_entry(number)

        # Initialize the boot environment package database.
        database = self._database(bootenv)

        # Determine which kernel package is installed in the boot environment.
        package = database.get_packages_by_name(self._linux)[-1]

        # Only delete the boot environment if it is currently not mounted on /.
        if bootenv != file_system.subvol:
            # Delete the boot environment.
            try:
                sh.btrfs.subvolume.delete(bootenv)
            except sh.ErrorReturnCode:
                raise timewarp.error.SubvolumeError(
                    f"Failed to delete boot environment {bootenv}")
        else:
            syslog.syslog(
                syslog.LOG_WARNING, f"Failed to delete boot environment "
                f"{bootenv}: Boot environment in use")

        remove_files = True

        # Now we are iterating over the remaining boot environments and check
        # if at least one of them is using the same kernel version.
        for bootenv_ in self._bootenvs.glob("*"):
            try:
                database_ = self._database(bootenv_)
            except timewarp.error.InitializationError as e:
                if not self._in_init:
                    syslog.syslog(
                        syslog.LOG_WARNING, f"Failed to initialize package "
                        f"database of boot environment {bootenv_}: "
                        f"{e.message}; not removing kernel or initrd images")

                # For some reason, the boot environment package database could
                # not be initialized.  As we cannot make sure that this kernel
                # version is not needed anymore, we leave it untouched.
                remove_files = False
                break

            try:
                package_ = database_.get_packages_by_name(self._linux)[-1]
            except timewarp.error.PackageNotFoundError:
                if not self._in_init:
                    syslog.syslog(
                        syslog.LOG_WARNING, f"Failed to query package "
                        f"database of boot environment {bootenv_}: Kernel "
                        f"package {self._linux} not found; not removing "
                        f"kernel or initrd images")

                # Same as the above.
                remove_files = False
                break

            if package_.version == package.version:
                remove_files = False
                break

        if remove_files:
            # No other boot environment is using the kernel which was used by
            # the boot environment we deleted earlier so we can safely remove
            # the kernel and initrd images.

            # Extend the default mapping with the kernel package.
            mapping = {
                **self._default_mapping,
                "linux": package
            }

            paths = set()

            # We are deleting each file individually, keeping track of the
            # directories to be removed.  We are not just deleting the
            # directories as they might contain files which we do not want to
            # touch.
            for file in self._configuration.filter_files(mapping).values():
                try:
                    file.unlink()
                    paths.add(file.parent)
                except FileNotFoundError:
                    if not self._in_init:
                        syslog.syslog(
                            syslog.LOG_WARNING, f"Failed to delete {file}: "
                            f"File not found")

            for path in paths:
                current = path

                while current != self._mount_point:
                    try:
                        current.rmdir()
                        current = current.parent
                    except FileNotFoundError:
                        if not self._in_init:
                            syslog.syslog(
                                syslog.LOG_WARNING, f"Failed to delete "
                                f"{path}: Directory not found")
                    except OSError:
                        # Fail silently if the directory is not empty.
                        break

    def _create_snapshot_error_handler(
            function: typing.Callable[..., int]) -> typing.Callable[..., int]:
        @functools.wraps(function)
        def decorator(
                self, *args: typing.Iterable[typing.Any],
                **kwargs: typing.Iterable[typing.Any]) -> int:
            try:
                return function(self, *args, **kwargs)
            except timewarp.error.InvalidPackageInformationError:
                syslog.syslog(
                    syslog.LOG_ERR, f"Failed to query root package database: "
                    f"Package information for kernel package {self._linux} is "
                    f"invalid")
            except timewarp.error.NoPreSnapshotError:
                syslog.syslog(
                    syslog.LOG_ERR, "Failed to create post-snapshot: "
                    "Attempting to create post-snapshot without pre-snapshot")
            except timewarp.error.PackageNotFoundError as e:
                syslog.syslog(
                    syslog.LOG_ERR, f"Failed to query root package database: "
                    f"Kernel package {self._linux} not found")
            except timewarp.error.SubvolumeError as e:
                syslog.syslog(syslog.LOG_ERR, e.message)
            except Exception as e:
                syslog.syslog(syslog.LOG_ERR, f"Unexpected error: {e}")

            return 0

        return decorator

    @_create_snapshot_error_handler
    def _create_snapshot(
            self, type: timewarp.service.snapper.SnapshotType) -> int:
        if timewarp.service.snapper.SnapshotType.PRE == type:
            # Create a pre-snapshot.
            snapshot = self._snapper.create_pre_snapshot(
                self._configuration.snapper.description, self._userdata)
        elif timewarp.service.snapper.SnapshotType.POST == type:
            # Create a post-snapshot.  Raises NoPreSnapshotError if no
            # pre-snapshot has been created earlier.
            snapshot = self._snapper.create_post_snapshot("", self._userdata)
        else:
            # Create a single snapshot.
            snapshot = self._snapper.create_single_snapshot(
                self._configuration.snapper.description, self._userdata)

        # This should normally only fail if you uninstalled your kernel.
        package = self._root_database.get_packages_by_name(self._linux)[-1]

        # Extend the default mapping with the snapshot and kernel package.
        mapping = {
            **self._default_mapping,
            "snapshot": snapshot,
            "linux": package
        }

        # Copy kernel and initrd images.
        for source, destination in self._configuration.filter_files(
                mapping).items():
            if destination.exists():
                continue

            path = destination.parent

            if not path.exists():
                path.mkdir(parents=True)

            try:
                shutil.copy2(source, destination)
            except FileNotFoundError:
                syslog.syslog(
                    syslog.LOG_WARNING, f"Failed to copy kernel or "
                    f"initrd image: Source file {source} not found")

        number = snapshot.number
        bootenv = self._bootenvs / str(number)

        # Create the boot environment.
        try:
            sh.btrfs.subvolume.snapshot(
                self._snapshots / str(number) / "snapshot", bootenv)
        except sh.ErrorReturnCode:
            raise timewarp.error.SubvolumeError(
                f"Failed to create boot environment {bootenv}")

        # Add the new boot loader entry.
        self._loader.add_entry(
            number, timewarp.service.boot.Entry(
                **self._configuration.format(
                    mapping, self._configuration.boot.entry)))

        return number

    def _monitor_handler(
            self, monitor: Gio.FileMonitor, child: Gio.File,
            other_file: Gio.File, event_type: Gio.FileMonitorEvent) -> None:
        # The final path component contains the snapshot number.
        try:
            number = int(pathlib.Path(child.get_path()).name)
        except ValueError:
            return

        bootenv = self._bootenvs / str(number)

        if Gio.FileMonitorEvent.DELETED == event_type and bootenv.exists():
            self._clean_up(number)

    def _signal_handler(self, number, frame) -> None:
        self._loop.quit()


def main(args: typing.List[str] = None) -> None:
    """Entry point."""
    if args is None:
        args = sys.argv[1:]

    try:
        # Initialize the Time Warp service and start it.
        service = Service()
        service.start()
    except timewarp.error.InitializationError as e:
        print(f"Failed to start timewarpd: {e.message}.")
        exit(-1)


if __name__ == "__main__":
    main()
