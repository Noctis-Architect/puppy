from __future__ import annotations

import importlib
import logging
import pkgutil
from functools import lru_cache

from app.core.module_api import BotModule

logger = logging.getLogger(__name__)

_MODULES_PACKAGE = "app.modules"


def _load_module_from_package(package_name: str) -> BotModule | None:
    try:
        package = importlib.import_module(package_name)
    except Exception:
        logger.exception("Failed importing module package %s", package_name)
        return None

    module_obj = getattr(package, "MODULE", None)
    if module_obj is None and hasattr(package, "get_module"):
        module_obj = package.get_module()

    if module_obj is None:
        logger.warning("Package %s has no MODULE export", package_name)
        return None

    if not isinstance(module_obj, BotModule):
        logger.warning("Package %s MODULE is not a BotModule instance", package_name)
        return None

    return module_obj


def discover_modules() -> list[BotModule]:
    """Import every subpackage under app.modules and collect BotModule instances."""
    modules: list[BotModule] = []
    package = importlib.import_module(_MODULES_PACKAGE)

    for _finder, name, is_pkg in pkgutil.iter_modules(package.__path__):
        if not is_pkg:
            continue
        full_name = f"{_MODULES_PACKAGE}.{name}"
        loaded = _load_module_from_package(full_name)
        if loaded is not None:
            modules.append(loaded)

    modules.sort(key=lambda m: (m.order, m.name))
    return modules


@lru_cache(maxsize=1)
def get_modules() -> tuple[BotModule, ...]:
    return tuple(discover_modules())


def clear_module_cache() -> None:
    get_modules.cache_clear()
