import re as _re
import sys as _sys
import types as _types
import warnings as _warnings

from protobuf import Enum as _ProtobufEnum
from protobuf import Message as _ProtobufMessage


class EnumWrapper:
    def __init__(self, cls):
        self._wrapped = cls
        self._original_names = {}
        desc = cls.desc() if hasattr(cls, "desc") else None
        if desc and hasattr(desc, "values"):
            for v in desc.values:
                self._original_names[v.name] = v.number
        else:
            for member in cls:
                self._original_names[member.name] = member.value

    @property
    def wrapped(self):
        _warnings.warn(
            "Accessing .wrapped is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._wrapped

    @wrapped.setter
    def wrapped(self, value):
        _warnings.warn(
            "Accessing .wrapped is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._wrapped = value

    def __repr__(self):
        return f"EnumWrapper of {self._wrapped!r}"

    def __getattr__(self, name):
        try:
            return getattr(self._wrapped, name)
        except AttributeError:
            val = self._original_names.get(name, None)
            if val is None:
                raise
            target = self._wrapped(val)
            _warnings.warn(
                f"Accessing enum value by original name '{name}' is deprecated. Use '{target.name}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return target

    def from_string(self, name):
        try:
            return self._wrapped[name]
        except (KeyError, ValueError):
            val = self._original_names.get(name, None)
            if val is None:
                raise ValueError(f"Unknown enum value: {name}") from None
            target = self._wrapped(val)
            _warnings.warn(
                f"Accessing enum value by original name '{name}' is deprecated. Use '{target.name}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return target

    def __getitem__(self, item):
        try:
            return self._wrapped[item]
        except KeyError:
            val = self._original_names.get(item, None)
            if val is None:
                raise
            target = self._wrapped(val)
            _warnings.warn(
                f"Accessing enum value by original name '{item}' is deprecated. Use '{target.name}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return target

    def __contains__(self, item):
        try:
            if isinstance(item, self._wrapped):
                return True
            if (
                hasattr(self._wrapped, "__members__")
                and item in self._wrapped.__members__
            ):
                return True
            if item in self._original_names:
                _warnings.warn(
                    f"Checking enum value by original name '{item}' is deprecated.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return True
            self._wrapped(item)
            return True
        except (ValueError, TypeError):
            return False

    def __len__(self):
        return len(self._wrapped)

    def __iter__(self):
        return iter(self._wrapped)

    def __call__(self, val):
        return self._wrapped(val)


def _find_enums(cls, prefix):
    results = {}
    for attr_name in dir(cls):
        if attr_name.startswith("_"):
            continue
        attr = getattr(cls, attr_name, None)
        if isinstance(attr, type):
            if issubclass(attr, _ProtobufEnum):
                results[f"{prefix}{attr_name}"] = attr
            elif issubclass(attr, _ProtobufMessage):
                results.update(_find_enums(attr, f"{prefix}{attr_name}"))
    return results


def _find_nested_messages(cls, prefix, display_prefix=None):
    """Discover nested message classes and return flat name -> (canonical_name, class) mapping."""
    if display_prefix is None:
        display_prefix = prefix
    results = {}
    for attr_name in dir(cls):
        if attr_name.startswith("_"):
            continue
        attr = getattr(cls, attr_name, None)
        if isinstance(attr, type) and issubclass(attr, _ProtobufMessage):
            flat_name = f"{prefix}{attr_name}"
            canonical_name = f"{display_prefix}.{attr_name}"
            results[flat_name] = (canonical_name, attr)
            results.update(_find_nested_messages(attr, flat_name, canonical_name))
    return results


def _capitalization_aliases(name):
    """Yield old-style capitalization variants (e.g. Vector3D for Vector3d)."""
    # 3d/2d -> 3D/2D
    m = _re.search(r"(\d)d$", name)
    if m:
        yield name[: m.start()] + m.group(1) + "D"
    # Uppercase acronyms that betterproto2 now keeps uppercase (CMYK, HSV, etc.)
    # were previously title-cased (Cmyk, Hsv, etc.)
    m = _re.match(r"^(.*?)([A-Z]{2,})$", name)
    if m:
        acronym = m.group(2)
        yield m.group(1) + acronym[0] + acronym[1:].lower()


def _patch_parse_methods(cls):
    if hasattr(cls, "from_binary"):

        def ParseFromString(cls_or_self, data):
            _warnings.warn(
                f"{cls.__name__}.ParseFromString is deprecated. Use {cls.__name__}.from_binary() instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            c = cls_or_self if isinstance(cls_or_self, type) else cls_or_self.__class__
            return c.from_binary(data)

        def parse(cls_or_self, data):
            _warnings.warn(
                f"{cls.__name__}.parse is deprecated. Use {cls.__name__}.from_binary() instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            c = cls_or_self if isinstance(cls_or_self, type) else cls_or_self.__class__
            return c.from_binary(data)

        cls.ParseFromString = classmethod(ParseFromString)
        cls.parse = classmethod(parse)


def setup_deprecation(
    module_globals=None, generated_module=None, module_name="betterosi"
):
    if generated_module is None:
        from .version_manager import DEFAULT_VERSION, load_generated_version

        generated_module = load_generated_version(DEFAULT_VERSION)

    if module_globals is None:
        mod = _sys.modules.get(module_name)
        if mod is not None:
            module_globals = mod.__dict__
        else:
            return {}, {}

    # 1. Enums wrapped in EnumWrapper
    all_enums = {}
    for name in getattr(generated_module, "__all__", []):
        cls = getattr(generated_module, name)
        if isinstance(cls, type) and issubclass(cls, _ProtobufMessage):
            all_enums.update(_find_enums(cls, name))

    for n, e in all_enums.items():
        module_globals[n] = EnumWrapper(e)

    # 2. Patch ParseFromString and parse on all message classes
    for c_name in getattr(generated_module, "__all__", []):
        c = getattr(generated_module, c_name)
        if isinstance(c, type) and issubclass(c, _ProtobufMessage):
            _patch_parse_methods(c)
            for _, nested_c in _find_nested_messages(c, c_name).values():
                _patch_parse_methods(nested_c)

    # 3. Capitalization aliases
    capitalization_map = {}
    for name in getattr(generated_module, "__all__", []):
        cls = getattr(generated_module, name)
        if isinstance(cls, type) and issubclass(cls, _ProtobufMessage):
            for alt in _capitalization_aliases(name):
                capitalization_map[alt] = (name, cls)

    # 4. Nested messages
    nested_messages_map = {}
    for name in getattr(generated_module, "__all__", []):
        cls = getattr(generated_module, name)
        if isinstance(cls, type) and issubclass(cls, _ProtobufMessage):
            nested_messages_map.update(_find_nested_messages(cls, name))

    existing_getattr = module_globals.get("__getattr__")

    def __getattr__(name: str):
        if name in capitalization_map:
            canonical, target_cls = capitalization_map[name]
            _warnings.warn(
                f"'{name}' is deprecated. Use '{canonical}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return target_cls
        if name in nested_messages_map:
            canonical, target_cls = nested_messages_map[name]
            _warnings.warn(
                f"'{name}' is deprecated. Use '{canonical}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return target_cls
        if name == "EnumWrapper":
            _warnings.warn(
                "'EnumWrapper' is deprecated.",
                DeprecationWarning,
                stacklevel=2,
            )
            return EnumWrapper
        if existing_getattr is not None:
            return existing_getattr(name)
        raise AttributeError(f"module '{module_name}' has no attribute '{name}'")

    existing_dir = module_globals.get("__dir__")

    def __dir__():
        base = list(module_globals.keys())
        if existing_dir is not None:
            base = existing_dir()
        extra = (
            set(capitalization_map.keys())
            | set(nested_messages_map.keys())
            | {"EnumWrapper"}
        )
        return sorted(set(base) | extra)

    module_globals["__getattr__"] = __getattr__
    module_globals["__dir__"] = __dir__

    return capitalization_map, nested_messages_map


setup = setup_deprecation


class _CallableModule(_types.ModuleType):
    def __call__(self, *args, **kwargs):
        return setup_deprecation(*args, **kwargs)


_sys.modules[__name__].__class__ = _CallableModule
