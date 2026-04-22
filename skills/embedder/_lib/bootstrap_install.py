"""OS-dispatched install command for the ORT shared library.

macOS → brew; Debian/Ubuntu Linux → apt-get. Other distros (Fedora dnf,
Arch pacman, Alpine apk) are not yet wired — extend the dispatch table
below when adding them.
"""
import platform

_MAC = (["brew", "install", "onnxruntime"], "brew")
_LINUX = (["sudo", "apt-get", "install", "-y", "libonnxruntime-dev"],
          "apt-get")


def install_cmd_for_os():
    return _LINUX if platform.system() == "Linux" else _MAC
