#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import json
import jsonschema
import os
import pathlib
import re
import typing

import timewarp.error
import timewarp.namespace
import timewarp.service.block


class Configuration(object):
    """Time Warp configuration."""

    _schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "boot",
            "bootenv",
            "package",
            "snapper",
            "snapshots"
        ],
        "properties": {
            "boot": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "entry",
                    "loader",
                    "mount_point"
                ],
                "properties": {
                    "boot_on_root": {
                        "type": "boolean"
                    },
                    "entry": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "linux"
                        ],
                        "properties": {
                            "title": {
                                "type": "string"
                            },
                            "version": {
                                "type": "string"
                            },
                            "machine_id": {
                                "type": "string"
                            },
                            "options": {
                                "type": "array",
                                "additionalItems": False,
                                "items": {
                                    "anyOf": [
                                        {
                                            "type": "string"
                                        },
                                        {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "patternProperties": {
                                                "^.*$": {
                                                    "type": "string",
                                                }
                                            }
                                        }
                                    ]
                                }
                            },
                            "architecture": {
                                "type": "string"
                            },
                            "linux": {
                                "type": "string"
                            },
                            "initrd": {
                                "type": "array",
                                "additionalItems": False,
                                "items": {
                                    "type": "string"
                                }
                            }
                        }
                    },
                    "loader": {
                        "type": "string"
                    },
                    "mount_point": {
                        "type": "string"
                    }
                }
            },
            "bootenv": {
                "type": "string"
            },
            "machine_id": {
                "type": "string"
            },
            "package": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "database",
                    "linux"
                ],
                "properties": {
                    "database": {
                        "type": "string"
                    },
                    "important": {
                        "type": "array",
                        "additionalItems": False,
                        "items": {
                            "type": "string"
                        }
                    },
                    "linux": {
                        "type": "string"
                    }
                }
            },
            "snapper": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "cleanup_algorithm",
                    "description",
                    "name"
                ],
                "properties": {
                    "cleanup_algorithm": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    },
                    "name": {
                        "type": "string"
                    }
                }
            },
            "snapshots": {
                "type": "string"
            }
        }
    }

    def __init__(self) -> None:
        # Load the configuration file from the first (most important)
        # configuration directory.  Fall back on /etc/xdg if no directory is
        # defined.  See also https://specifications.freedesktop.org/
        # basedir-spec/basedir-spec-latest.html.
        xdg_config_dirs = os.getenv("XDG_CONFIG_DIRS")
        xdg_config_dir = xdg_config_dirs.split(":")[0] \
            if xdg_config_dirs else "/etc/xdg"
        configuration = pathlib.Path(
            xdg_config_dir) / "timewarp" / "timewarp.conf"

        try:
            with open(configuration, "r") as f:
                self._instance = json.load(
                    f, object_hook=lambda kwargs: timewarp.namespace.Namespace(
                        **kwargs))
        except FileNotFoundError:
            raise timewarp.error.InitializationError(
                f"Configuration file {configuration} not found")

        # Validate the configuration file using JSON Schema.
        try:
            jsonschema.validate(self._instance, Configuration._schema)
        except jsonschema.exceptions.ValidationError as e:
            raise timewarp.error.InitializationError(
                f"Invalid configuration: {e.message}")

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self._instance, name)

    def filter_files(
            self, mapping: typing.Mapping[
                str, typing.Any]) -> \
            typing.Mapping[pathlib.Path, pathlib.Path]:
        """
        Returns a source file: destination file mapping for all kernel and
        initrd images referenced by the configured boot loader entry whose path
        contains at least one non-constant replacement field.

        Keyword arguments:
        mapping -- a Mapping type containing the field names and values
        """
        boot = self._instance.boot
        boot_on_root = boot.boot_on_root if "boot_on_root" in boot else False
        entry = boot.entry
        mount_point = pathlib.Path(boot.mount_point)
        result = {}

        if boot_on_root:
            root_file_system = timewarp.service.block.FileSystem("/")

        for filename in [entry.linux] + entry.initrd:
            if list(filter(lambda replacement_field: replacement_field not in [
                    "architecture", "machine_id"],
                    re.findall(r"\{(.*?)\}", filename))):
                file = pathlib.Path(eval(f"f\"{filename}\"", {}, mapping))

                # When /boot is located on root, chances are that the boot
                # loader needs the subvolume and/or /boot mount point in order
                # to be able to locate the current image file.  We just want
                # to copy the image file to /boot so we do not need this
                # information and can strip the subvolume and/or /boot mount
                # point from the destination file name.
                if boot_on_root:
                    try:
                        file = file.relative_to(root_file_system.subvol)
                    except ValueError:
                        pass

                    try:
                        file = file.relative_to(
                            mount_point.relative_to(mount_point.anchor))
                    except ValueError:
                        pass

                result[mount_point / file.name] = \
                    mount_point / file.relative_to(file.anchor)

        return result

    def format(
            self, mapping: typing.Mapping[str, typing.Any],
            root: typing.Any = None) -> typing.Any:
        """
        Recursively substitutes all replacement fields in any format string
        found in root with values from mapping.  Non-string values are copied
        unchanged.

        Keyword arguments:
        mapping -- a Mapping type containing the field names and values
        root    -- Any type containing a format string (default None)
        """
        if root is None:
            root = self._instance

        if isinstance(root, str):
            result = eval(f"f\"{root}\"", {}, mapping)
        elif isinstance(root, typing.Mapping):
            result = type(root)()

            for name, value in root.items():
                result[name] = self.format(mapping, value)
        elif isinstance(root, typing.Iterable):
            result = type(root)()

            for item in root:
                result.append(self.format(mapping, item))
        else:
            result = root

        return result
