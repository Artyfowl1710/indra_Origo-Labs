"""Compatibility shim for Python: exposes tomli or stdlib tomllib."""
try:
    from tomli import *
    from tomli import TOMLDecodeError
except ImportError:
    try:
        import _tomllib as _t
        loads = _t.loads
        TOMLDecodeError = _t.TOMLDecodeError
    except ImportError:
        pass

