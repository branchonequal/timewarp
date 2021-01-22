#
# Time Warp
# Copyright 2020, 2021 Thomas Müller
# All rights reserved.
#

import setuptools


setuptools.setup(
    name="timewarp",
    version="0.0.1b1",
    description="Fully automated Snapper snapshot and boot environment "
    "creation.",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: System :: Systems Administration"
    ],
    url="https://branchonequal.com",
    keywords="alpm btrfs dpkg grub snapper systemd-boot",
    project_urls={
        "Documentation": "https://github.com/branchonequal/timewarp",
        "Source": "https://github.com/branchonequal/timewarp"
    },
    author="Thomas Müller",
    author_email="timewarp-dev@branchonequal.com",
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    install_requires=[
        "argh",
        "jsonschema",
        "pydbus",
        "PyGObject",
        "sh"
    ],
    entry_points={
        "console_scripts": [
            "timewarp=timewarp.client.__main__:main",
            "timewarpd=timewarp.service.__main__:main"
        ]
    },
    zip_safe=True,
    python_requires=">=3.6")
