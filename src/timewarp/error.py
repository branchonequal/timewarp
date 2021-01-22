#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#


class DBusError(Exception):
    """D-Bus error."""

    def __init__(self, code: int) -> None:
        super().__init__()
        self.code = code

    def __str__(self) -> str:
        if 1 == self.code:
            return "No memory"
        elif 2 == self.code:
            return "Service unknown"
        elif 3 == self.code:
            return "Name has no owner"
        elif 4 == self.code:
            return "No reply"
        elif 5 == self.code:
            return "I/O error"
        elif 6 == self.code:
            return "Bad address"
        elif 7 == self.code:
            return "Not supported"
        elif 8 == self.code:
            return "Limits exceeded"
        elif 9 == self.code:
            return "Access denied"
        elif 10 == self.code:
            return "Authentication failed"
        elif 11 == self.code:
            return "No server"
        elif 12 == self.code:
            return "Timeout"
        elif 13 == self.code:
            return "No network"
        elif 14 == self.code:
            return "Address in use"
        elif 15 == self.code:
            return "Disconnected"
        elif 16 == self.code:
            return "Invalid arguments"
        elif 17 == self.code:
            return "File not found"
        elif 18 == self.code:
            return "File exists"
        elif 19 == self.code:
            return "Unknown method"
        elif 20 == self.code:
            return "Timed out"
        elif 21 == self.code:
            return "Match rule not found"
        elif 22 == self.code:
            return "Match rule invalid"
        elif 23 == self.code:
            return "Spawn exec() failed"
        elif 24 == self.code:
            return "Spawn fork() failed"
        elif 25 == self.code:
            return "Spawn child exited"
        elif 26 == self.code:
            return "Spawn child signaled"
        elif 27 == self.code:
            return "Spawn failed"
        elif 28 == self.code:
            return "Spawn setup failed"
        elif 29 == self.code:
            return "Spawn config invalid"
        elif 30 == self.code:
            return "Spawn service invalid"
        elif 31 == self.code:
            return "Spawn service not found"
        elif 32 == self.code:
            return "Spawn permissions invalid"
        elif 33 == self.code:
            return "Spawn file invalid"
        elif 34 == self.code:
            return "Spawn no memory"
        elif 35 == self.code:
            return "Unix process ID unknown"
        elif 36 == self.code:
            return "Invalid signature"
        elif 37 == self.code:
            return "Invalid file content"
        elif 38 == self.code:
            return "SELinux security context unknown"
        elif 39 == self.code:
            return "ADT audit data unknown"
        elif 40 == self.code:
            return "Object path in use"
        elif 41 == self.code:
            return "Unknown object"
        elif 42 == self.code:
            return "Unknown interface"
        elif 43 == self.code:
            return "Unknown property"
        elif 44 == self.code:
            return "Property read-only"
        else:
            return "Failed"


class InitializationError(Exception):
    """Initialization error."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message


class InvalidPackageInformationError(Exception):
    """Invalid package information error."""

    pass


class NoPreSnapshotError(Exception):
    """No pre-snapshot error."""

    pass


class PackageNotFoundError(Exception):
    """Package not found error."""

    pass


class SubvolumeError(Exception):
    """Subvolume error."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message
