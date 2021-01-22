#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import typing


class Namespace(dict):
    """Dictionary subclass which exposes its key: value pairs as attributes."""

    def __init__(self, **kwargs: typing.Iterable[typing.Any]) -> None:
        super().__init__(kwargs)

    def __getattr__(self, name: str) -> typing.Any:
        return self.get(name)
