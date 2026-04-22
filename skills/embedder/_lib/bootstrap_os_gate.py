"""OS gate for bootstrap — dispatch return codes for Windows/unsupported."""

WIN_UNSUPPORTED = 10
PARTIAL = 20
SUPPORTED = {"Darwin", "Linux"}


def handle_unsupported(system):
    if system == "Windows":
        return _skip()
    return _unsupported(system)


def _skip():
    print("embedder bootstrap skipped (Windows not supported — use WSL)")
    return WIN_UNSUPPORTED


def _unsupported(system):
    print(f"WARN: Unsupported OS: {system}. Supported: macOS, Linux.")
    return PARTIAL
