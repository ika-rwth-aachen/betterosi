import sys
import warnings
from typing import Any

from .io import (  # noqa: F401
    OSI_CHANNEL_DESCRIPTION_KEY,
    OSI_CHANNEL_OSI_VERSION_KEY,
    OSI_CHANNEL_PROTOBUF_VERSION_KEY,
    OSI_TRACE_METADATA_NAME,
    Writer,
    extract_timestamp_from_filename,
    gen2betterosi,
    iter_osi_trace_file,
    load_descriptor_set,
    prepare_channel_metadata,
    prepare_required_file_metadata,
    read,
    read_channel_metadata,
    read_file_metadata,
)
from .mcap_reader import MESSAGES_TYPE, BetterOsiDecoderFactory  # noqa: F401
from .version_manager import (
    DEFAULT_VERSION,
    get_available_versions,
    get_version_module,
    version_to_module_name,
)

__version__ = "0.8.5"
__version_osi__ = DEFAULT_VERSION

# Load default version (3.8.0) and populate betterosi's top-level namespace
_default_version_module = get_version_module(DEFAULT_VERSION)

# Re-export all non-private attributes from default version (except EnumWrapper)
for _k, _v in _default_version_module.__dict__.items():
    if not _k.startswith("_") and _k != "EnumWrapper" and _k not in globals():
        globals()[_k] = _v

# Discover and register all available versions (e.g. v3_5_0, v3_8_0)
_available_versions = get_available_versions()
for _ver in _available_versions:
    _attr_name = version_to_module_name(_ver)
    _v_mod = get_version_module(_ver)
    globals()[_attr_name] = _v_mod
    sys.modules[f"betterosi.{_attr_name}"] = _v_mod


def __getattr__(name: str) -> Any:
    # 1. Version access like v3_5_0 or v3_8_0 (dynamically discoverable)
    if name.startswith("v") and "_" in name:
        try:
            mod = get_version_module(name)
            globals()[name] = mod
            sys.modules[f"betterosi.{name}"] = mod
            return mod
        except (ValueError, KeyError, ModuleNotFoundError):
            pass

    # 2. Direct access to EnumWrapper
    if name == "EnumWrapper":
        from .deprecation import EnumWrapper

        warnings.warn(
            "'EnumWrapper' is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        return EnumWrapper

    # 3. Check capitalization aliases and nested messages on default version
    try:
        return getattr(_default_version_module, name)
    except AttributeError:
        raise AttributeError(f"module 'betterosi' has no attribute '{name}'") from None


def __dir__():
    base = set(globals().keys())
    base |= set(dir(_default_version_module))
    for v in get_available_versions():
        base.add(version_to_module_name(v))
    return sorted(base)
