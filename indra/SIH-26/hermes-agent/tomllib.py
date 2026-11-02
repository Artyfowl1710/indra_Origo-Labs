"""Compatibility shim that does not shadow Python 3.11+ stdlib tomllib."""
import sys as _sys
if _sys.version_info >= (3, 11):
    import importlib.util as _util
    import sysconfig as _sysconfig
    from pathlib import Path as _Path
    _root = _Path(_sysconfig.get_path("stdlib")) / "tomllib"
    _spec = _util.spec_from_file_location("_origo_stdlib_tomllib", _root / "__init__.py", submodule_search_locations=[str(_root)])
    _module = _util.module_from_spec(_spec)
    _sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
    load, loads, TOMLDecodeError = _module.load, _module.loads, _module.TOMLDecodeError
else:
    from tomli import load, loads, TOMLDecodeError
__all__ = ["load", "loads", "TOMLDecodeError"]
