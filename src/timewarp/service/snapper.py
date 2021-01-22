#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import datetime
import enum
from gi.repository import GLib
import pydbus
import typing

import timewarp.error


class Snapshot(object):
    """Snapper snapshot."""

    def __init__(
            self, number: int, type: int, pre_number: int, date: int,
            user: int, description: str, cleanup_algorithm: str,
            userdata: typing.Mapping[str, str]) -> None:
        self.number = number
        self.type = SnapshotType(type)
        self.pre_number = pre_number
        self.date = datetime.datetime.fromtimestamp(date)
        self.user = user
        self.description = description
        self.cleanup_algorithm = cleanup_algorithm
        self.userdata = userdata


class Snapper(object):
    """Wrapper around the Snapper D-Bus service."""

    def __init__(self, name: str, cleanup_algorithm: str) -> None:
        self._name = name
        self._cleanup_algorithm = cleanup_algorithm
        self._pre_number = None

        # Connect to the Snapper D-Bus service.
        try:
            self._service = pydbus.SystemBus().get("org.opensuse.Snapper")
        except GLib.Error:
            raise timewarp.error.InitializationError(
                "snapperd is not running")

    def create_pre_snapshot(
            self, description: str,
            userdata: typing.Mapping[str, str]) -> Snapshot:
        """
        Creates a new pre-snapshot, returning the snapshot.

        Keyword arguments:
        description -- the snapshot description
        userdata    -- a dictionary containing optional user data
        """
        if not self._pre_number:
            self._pre_number = self._service.CreatePreSnapshot(
                self._name, description, self._cleanup_algorithm, userdata)

        return self._get_snapshot(self._pre_number)

    def create_post_snapshot(
            self, description: str,
            userdata: typing.Mapping[str, str]) -> Snapshot:
        """
        Creates a new post-snapshot, returning the snapshot.

        Keyword arguments:
        description -- the snapshot description
        userdata    -- a dictionary containing optional user data
        """
        if self._pre_number:
            post_number = self._service.CreatePostSnapshot(
                self._name, self._pre_number, description,
                self._cleanup_algorithm, userdata)
            self._pre_number = None
            return self._get_snapshot(post_number)
        else:
            raise timewarp.error.NoPreSnapshotError

    def create_single_snapshot(
            self, description: str,
            userdata: typing.Mapping[str, str]) -> Snapshot:
        """
        Creates a new single snapshot, returning the snapshot.

        Keyword arguments:
        description -- the snapshot description
        userdata    -- a dictionary containing optional user data
        """
        number = self._service.CreateSingleSnapshot(
            self._name, description, self._cleanup_algorithm, userdata)
        return self._get_snapshot(number)

    def _get_snapshot(self, number: int) -> Snapshot:
        return Snapshot(*self._service.GetSnapshot(self._name, number))


class SnapshotType(enum.Enum):
    """Snapper snapshot type."""

    SINGLE = 0
    PRE = 1
    POST = 2

    def __str__(self) -> str:
        return self.name.lower()
