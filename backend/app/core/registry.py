"""Name -> implementation registries. config.yaml selects implementations by these names.

Usage:
    @routers.register("my_router")
    class MyRouter: ...

    routers.get("my_router")  # -> MyRouter
"""
import importlib
import pkgutil
from collections.abc import Callable


class Registry[T]:
    def __init__(self, kind: str):
        self.kind = kind
        self._items: dict[str, T] = {}

    def register(self, name: str) -> Callable[[T], T]:
        def deco(obj: T) -> T:
            if name in self._items and self._items[name] is not obj:
                raise ValueError(f"{self.kind} '{name}' is already registered")
            self._items[name] = obj
            return obj

        return deco

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError:
            known = ", ".join(sorted(self._items)) or "none"
            raise KeyError(f"unknown {self.kind} '{name}' (registered: {known})") from None

    def names(self) -> list[str]:
        return sorted(self._items)

    def __contains__(self, name: object) -> bool:
        return name in self._items


def import_submodules(package: str) -> None:
    """Import every module in a package so their @register decorators run."""
    pkg = importlib.import_module(package)
    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{package}.{mod.name}")


steps: Registry[type] = Registry("pipeline step")
checkers: Registry[type] = Registry("checker")
knowledge_models: Registry[type] = Registry("knowledge model")
preference_models: Registry[type] = Registry("preference model")
routers: Registry[type] = Registry("router")
retrievers: Registry[type] = Registry("retriever")
session_stores: Registry[type] = Registry("session store")
