# pragma: no cover
import io
import os
import re

from setuptools import setup

this_directory = os.path.abspath(os.path.dirname(__file__))

with io.open(os.path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

package = dict()
with io.open(
    os.path.join(this_directory, "flaresolverr_session.py"), encoding="utf-8"
) as f:
    for line in f:
        match = re.match(r"(__\w+?__)\s*=\s*(.+)$", line)
        if match and match.group(1) != "__all__":
            package[match.group(1)] = eval(match.group(2))

setup(
    name=package["__title__"],
    version=package["__version__"],
    author=package["__author__"],
    author_email=package["__author_email__"],
    url=package["__url__"],
    description=package["__description__"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    py_modules=["flaresolverr_session"],
    python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, !=3.5.*",
    install_requires=[
        "requests",
    ],
    extras_require={
        "dev": [
            "pytest",
            "mock;python_version<'3'",
        ],
    },
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
