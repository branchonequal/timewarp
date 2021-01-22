#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import argh
import gi.repository
import os
import pydbus
import re
import select
import sys
import typing

import timewarp.configuration
import timewarp.error


class Client(object):
    """Time Warp command line client."""

    def __init__(self) -> None:
        # Load the configuration.  Raises InitializationError on error.
        self._configuration = timewarp.configuration.Configuration()

        # Connect to the Time Warp service.
        try:
            self._service = pydbus.SystemBus().get(
                "com.branchonequal.TimeWarp")
        except gi.repository.GLib.Error:
            raise timewarp.error.InitializationError(
                "timewarpd is not running")

        # Create the set of important packages.
        self._important = set(self._configuration.package.important) \
            if "important" in self._configuration.package else set()

    @argh.arg("-t", "--type", choices=["pre", "post", "single"], required=True)
    def create(self, type: str = None) -> None:
        """
        Creates a new pre-, post- or single snapshot.

        Keyword arguments:
        type -- "pre", "post" or "single" depending on the snapshot type
        """
        if type in ["pre", "single"]:
            packages = set()

            # Read the set of packages to be updated from stdin.
            while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                buffer = sys.stdin.read().strip()

                if not buffer:
                    break

                packages |= set(re.split(r"\s", buffer))

            if "pre" == type:
                number = self._service.CreatePreSnapshot(
                    packages & self._important)
            else:
                number = self._service.CreateSingleSnapshot(
                    packages & self._important)
        else:
            number = self._service.CreatePostSnapshot()

        if not number:
            print("Operation failed. Check the syslog for details.")
            exit(-1)


def main(args: typing.List[str] = None) -> None:
    """Entry point."""
    if args is None:
        args = sys.argv[1:]

    if "DISABLE_TIMEWARP" not in os.environ:
        try:
            # Initialize the Time Warp client.
            client = Client()

            # Process command line arguments.
            parser = argh.ArghParser(prog="timewarp")
            parser.add_commands([client.create])
            parser.dispatch()
        except timewarp.error.InitializationError as e:
            print(f"Failed to start timewarp: {e.message}.")
            exit(-1)


if __name__ == "__main__":
    main()
