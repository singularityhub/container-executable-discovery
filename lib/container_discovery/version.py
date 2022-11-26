__author__ = "Vanessa Sochat"
__copyright__ = "Copyright 2022, Vanessa Sochat"
__license__ = "MPL 2.0"

__version__ = "0.0.0"
AUTHOR = "Vanessa Sochat"
EMAIL = "vsoch@users.noreply.github.com"
NAME = "container_discovery"
PACKAGE_URL = "https://github.com/singularityhub/container-executable-discovery"
KEYWORDS = "container, executables, docker"
DESCRIPTION = "GitHub actions Python library for discovering container executables."
LICENSE = "LICENSE"

################################################################################
# Global requirements

INSTALL_REQUIRES = (
    ("container-guts", {"min_version": None}),
    ("pipelib", {"min_version": None}),
    ("requests", {"min_version": None}),
    ("beautifulsoup4", {"min_version": None}),
    ("packaging", {"min_version": None}),
)

TESTS_REQUIRES = (("pytest", {"min_version": "4.6.2"}),)

################################################################################
# Submodule Requirements

INSTALL_REQUIRES_ALL = INSTALL_REQUIRES + TESTS_REQUIRES
