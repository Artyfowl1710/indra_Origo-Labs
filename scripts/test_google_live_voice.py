"""Compatibility entry point: real-provider acceptance now uses the local bridge."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("test_live_bridge_provider.py")), run_name="__main__")
