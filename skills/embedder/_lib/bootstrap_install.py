"""OS-dispatched install command for the ORT shared library.

macOS → brew; Debian/Ubuntu Linux → apt-get. Unknown OSes raise
UnsupportedOSError instead of silently routing to macOS.
"""
import platform

from embedder._lib.bootstrap_errors import UnsupportedOSError

_MAC = (["brew", "install", "onnxruntime"], "brew")
_LINUX = (["sudo", "apt-get", "install", "-y", "libonnxruntime-dev"],
          "apt-get")
_DISPATCH = {"Darwin": _MAC, "Linux": _LINUX}


def install_cmd_for_os():
    system = platform.system()
    if system not in _DISPATCH:
        raise UnsupportedOSError(
            f"Unsupported OS: {system}. Supported: macOS, Linux.")
    return _DISPATCH[system]
