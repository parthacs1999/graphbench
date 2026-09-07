import platform
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version


def get_package_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "not installed"


def collect_environment_metadata() -> dict:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "system": {
            "operating_system": platform.system(),
            "operating_system_release": platform.release(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or "not reported",
        },
        "packages": {
            "networkx": get_package_version("networkx"),
            "ladybug": get_package_version("ladybug"),
            "streamlit": get_package_version("streamlit"),
            "pandas": get_package_version("pandas"),
            "altair": get_package_version("altair"),
            "psutil": get_package_version("psutil"),
        },
    }
