"""Save → modify → restore os.environ entries. Shared test helper.

Constructed with a dict mapping env-var name -> new value. A value of
None removes the key during the block. Exit restores every key to its
pre-enter state (including absence).
"""
import os


class EnvSandbox:
    def __init__(self, updates):
        self._updates = updates
        self._saved = {}

    def __enter__(self):
        for key, value in self._updates.items():
            self._saved[key] = os.environ.get(key)
            self._apply(key, value)
        return self

    def __exit__(self, *_):
        for key, prior in self._saved.items():
            self._apply(key, prior)

    def _apply(self, key, value):
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
