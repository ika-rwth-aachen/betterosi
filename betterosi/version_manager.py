import importlib.resources
import importlib.util
import re
import sys
import types
import warnings
from pathlib import Path

from .deprecation import EnumWrapper, setup_deprecation
from .io import (
    gen2betterosi,
    iter_osi_trace_file,
    load_descriptor_set,
    make_version_decoder_factory,
    make_version_read,
    make_version_writer,
)
from .mcap_reader import MESSAGES_TYPE

DEFAULT_VERSION = "3.8.0"

_GENERATED_MODULES: dict[str, types.ModuleType] = {}
_VERSION_MODULES: dict[str, "VersionModule"] = {}


def version_to_module_name(version: str) -> str:
    """Convert version string like '3.5.0' to module name 'v3_5_0'."""
    clean = version.lstrip("v").replace(".", "_")
    return f"v{clean}"


def module_name_to_version(name: str) -> str:
    """Convert module name like 'v3_5_0' to version string '3.5.0'."""
    clean = name.lstrip("v").replace("_", ".")
    return clean


def get_available_versions() -> list[str]:
    """Find all available generated OSI versions sorted chronologically."""
    gen_dir = Path(__file__).resolve().parent / "generated"
    if not gen_dir.exists():
        return [DEFAULT_VERSION]

    versions = []
    for d in gen_dir.iterdir():
        if (
            d.is_dir()
            and re.match(r"^\d+(\.\d+)*$", d.name)
            and (
                (d / "osi3_descriptor_set.pb").exists() or (d / "__init__.py").exists()
            )
        ):
            versions.append(d.name)

    versions.sort(key=lambda v: [int(x) if x.isdigit() else x for x in v.split(".")])
    return versions if versions else [DEFAULT_VERSION]


def load_generated_version(version: str) -> types.ModuleType:
    """Load the raw generated protobuf package for a specific version."""
    version = module_name_to_version(version)
    if version in _GENERATED_MODULES:
        return _GENERATED_MODULES[version]

    mod_name = f"betterosi.generated._{version_to_module_name(version)}"
    init_path = Path(__file__).resolve().parent / "generated" / version / "__init__.py"

    if not init_path.exists():
        raise ModuleNotFoundError(
            f"Generated protobuf code for OSI version '{version}' not found at {init_path}. "
            "Please run 'python gen_protos.py' to generate it."
        )

    spec = importlib.util.spec_from_file_location(
        mod_name,
        str(init_path),
        submodule_search_locations=[str(init_path.parent)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load generated module spec for {init_path}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    _GENERATED_MODULES[version] = mod
    return mod


class VersionModule(types.ModuleType):
    """Module-like object representing a specific OSI version of betterosi."""

    def __init__(
        self,
        name: str,
        version: str,
        generated_mod: types.ModuleType,
        doc: str | None = None,
    ):
        super().__init__(name, doc)
        self.__version_osi__ = version
        self.version = version
        self._generated = generated_mod
        self._capitalization_map: dict[str, tuple[str, type]] = {}
        self._nested_messages_map: dict[str, tuple[str, type]] = {}

    def __getattr__(self, name: str):
        if name in self._capitalization_map:
            canonical, target_cls = self._capitalization_map[name]
            warnings.warn(
                f"'{name}' is deprecated. Use '{canonical}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return target_cls
        if name in self._nested_messages_map:
            canonical, target_cls = self._nested_messages_map[name]
            warnings.warn(
                f"'{name}' is deprecated. Use '{canonical}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return target_cls
        if name == "EnumWrapper":
            warnings.warn(
                "'EnumWrapper' is deprecated.",
                DeprecationWarning,
                stacklevel=2,
            )
            return EnumWrapper
        # Cross-version access support, e.g. v3_5_0.v3_8_0
        if name.startswith("v") and "_" in name:
            try:
                return get_version_module(name)
            except (ValueError, KeyError, ModuleNotFoundError):
                pass
        raise AttributeError(f"module '{self.__name__}' has no attribute '{name}'")

    def __dir__(self):
        base = set(super().__dir__())
        extra = (
            set(self._capitalization_map.keys())
            | set(self._nested_messages_map.keys())
            | {"EnumWrapper"}
        )
        return sorted(base | extra)


def get_version_module(version_or_name: str) -> VersionModule:
    """Get or construct a VersionModule for the specified version (e.g. '3.5.0' or 'v3_5_0')."""
    version = module_name_to_version(version_or_name)
    mod_attr = version_to_module_name(version)
    full_mod_name = f"betterosi.{mod_attr}"

    if version in _VERSION_MODULES:
        return _VERSION_MODULES[version]

    gen_mod = load_generated_version(version)
    v_mod = VersionModule(
        full_mod_name,
        version,
        gen_mod,
        doc=f"betterosi bindings for ASAM OSI {version}",
    )

    # Re-export all classes from generated module
    all_names = list(getattr(gen_mod, "__all__", []))
    for item_name in all_names:
        setattr(v_mod, item_name, getattr(gen_mod, item_name))

    # Setup deprecation, enums, ParseFromString patches
    cap_map, nest_map = setup_deprecation(
        v_mod.__dict__, generated_module=gen_mod, module_name=full_mod_name
    )
    v_mod._capitalization_map = cap_map
    v_mod._nested_messages_map = nest_map

    # Setup version-bound I/O components
    descriptor_set = load_descriptor_set(version)
    v_mod.Writer = make_version_writer(version, descriptor_set=descriptor_set)
    v_mod.read = make_version_read(version, v_mod)
    v_mod.BetterOsiDecoderFactory = make_version_decoder_factory(version, v_mod)
    v_mod.MESSAGES_TYPE = MESSAGES_TYPE
    v_mod.gen2betterosi = gen2betterosi
    v_mod.iter_osi_trace_file = iter_osi_trace_file

    # Build __all__
    all_exports = set(all_names) | {
        "Writer",
        "read",
        "BetterOsiDecoderFactory",
        "MESSAGES_TYPE",
        "gen2betterosi",
        "iter_osi_trace_file",
        "version",
        "__version_osi__",
    }
    # Add EnumWrapper enums
    for k, v in v_mod.__dict__.items():
        if isinstance(v, EnumWrapper):
            all_exports.add(k)

    v_mod.__all__ = sorted(all_exports)

    # Register in sys.modules so 'import betterosi.v3_5_0' and 'from betterosi.v3_5_0 import ...' work
    sys.modules[full_mod_name] = v_mod
    _VERSION_MODULES[version] = v_mod
    return v_mod
