import re as _re
import sys as _sys
import types as _types
import warnings as _warnings

from protobuf import Enum as _ProtobufEnum
from protobuf import Message as _ProtobufMessage
from protobuf import merge_from_binary as _merge_from_binary


def _value_prefixes(member_name: str):
    if member_name.startswith("TYPE_"):
        suffix = member_name[5:]
    elif member_name.startswith("SUBTYPE_"):
        suffix = member_name[8:]
    else:
        suffix = member_name
    return f"TYPE_{suffix}", f"SUBTYPE_{suffix}"


class _DeprecatedEnumAttr:
    def __init__(self, target, alias):
        self.target = target
        self.alias = alias

    def __get__(self, instance, owner):
        _warnings.warn(
            f"Accessing enum value by original name '{self.alias}' is deprecated. Use '{self.target.name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.target


class _DeprecatedEnumType(type(_ProtobufEnum)):
    def __getitem__(cls, name):
        try:
            return super().__getitem__(name)
        except KeyError:
            dep_map = getattr(cls, "_deprecation_map", None)
            if dep_map and name in dep_map:
                target = dep_map[name]
                _warnings.warn(
                    f"Accessing enum value by original name '{name}' is deprecated. Use '{target.name}' instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return target
            raise

    def __contains__(cls, item):
        try:
            if super().__contains__(item):
                return True
        except TypeError:
            pass
        if (
            isinstance(item, str)
            and hasattr(cls, "__members__")
            and item in cls.__members__
        ):
            return True
        dep_map = getattr(cls, "_deprecation_map", None)
        if dep_map and item in dep_map:
            _warnings.warn(
                f"Checking enum value by original name '{item}' is deprecated.",
                DeprecationWarning,
                stacklevel=2,
            )
            return True
        return False


def _patch_enum(cls):
    if not isinstance(cls, type) or not issubclass(cls, _ProtobufEnum):
        return

    dep_map = cls.__dict__.get("_deprecation_map", None)
    if dep_map is None:
        dep_map = {}
        cls._deprecation_map = dep_map

    desc = cls.desc() if hasattr(cls, "desc") else None
    if desc and hasattr(desc, "values"):
        for v in desc.values:
            try:
                target = cls(v.number)
                dep_map.setdefault(v.name, target)
            except (ValueError, KeyError):
                pass

    for member in cls:
        t_name, st_name = _value_prefixes(member.name)
        dep_map.setdefault(t_name, member)
        dep_map.setdefault(st_name, member)

    for alias, target in dep_map.items():
        if alias not in cls.__dict__:
            setattr(cls, alias, _DeprecatedEnumAttr(target, alias))

    if not isinstance(cls.__class__, _DeprecatedEnumType):
        try:
            cls.__class__ = _DeprecatedEnumType
        except TypeError:
            pass


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

        for member in cls:
            self._original_names.setdefault(member.name, member.value)
            t_name, st_name = _value_prefixes(member.name)
            self._original_names.setdefault(t_name, member.value)
            self._original_names.setdefault(st_name, member.value)

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
        if hasattr(self._wrapped, "__members__") and name in self._wrapped.__members__:
            return getattr(self._wrapped, name)
        val = self._original_names.get(name, None)
        if val is None:
            return getattr(self._wrapped, name)
        target = self._wrapped(val)
        _warnings.warn(
            f"Accessing enum value by original name '{name}' is deprecated. Use '{target.name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return target

    def from_string(self, name):
        if hasattr(self._wrapped, "__members__") and name in self._wrapped.__members__:
            return self._wrapped[name]
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
        if hasattr(self._wrapped, "__members__") and item in self._wrapped.__members__:
            return self._wrapped[item]
        val = self._original_names.get(item, None)
        if val is None:
            raise KeyError(item)
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

    def __dir__(self):
        base = set(super().__dir__())
        base |= set(dir(self._wrapped))
        base |= set(self._original_names.keys())
        return sorted(base)


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


class _ClassOrInstanceMethod:
    """Descriptor that passes the class or the instance, depending on how it is accessed."""

    def __init__(self, func):
        self._func = func

    def __get__(self, obj, objtype=None):
        # MethodType does not add a Python stack frame, so the shim's
        # ``stacklevel=2`` still points at the caller.
        return _types.MethodType(self._func, obj if obj is not None else objtype)


def _parse_into(cls_or_self, data):
    """Decode ``data``.

    Called on the class, this returns a new message. Called on an instance, it
    clears that instance, fills it in place, and returns it.
    """
    if isinstance(cls_or_self, type):
        return cls_or_self.from_binary(data)

    msg = cls_or_self
    for field in msg.desc().fields:
        msg.clear_field(field.name)
    unknown = getattr(msg, "_unknown_fields", None)
    if unknown:
        unknown.clear()
    _merge_from_binary(msg, data)
    return msg


def _patch_parse_methods(cls):
    if hasattr(cls, "from_binary"):

        def _make_parse_shim(method_name):
            def shim(cls_or_self, data):
                _warnings.warn(
                    f"{cls.__name__}.{method_name} is deprecated. Use {cls.__name__}.from_binary() instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return _parse_into(cls_or_self, data)

            shim.__name__ = method_name
            return _ClassOrInstanceMethod(shim)

        cls.ParseFromString = _make_parse_shim("ParseFromString")
        cls.parse = _make_parse_shim("parse")

    if hasattr(cls, "to_binary"):

        def __bytes__(self):
            _warnings.warn(
                f"bytes({cls.__name__}) is deprecated. Use {cls.__name__}.to_binary() instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.to_binary()

        cls.__bytes__ = __bytes__


MISSING = object()
"""Sentinel returned by :func:`resolve_deprecated_name` when ``name`` is not an alias."""


def resolve_deprecated_name(
    name: str,
    capitalization_map: dict,
    nested_messages_map: dict,
    stacklevel: int = 3,
):
    """Resolve a deprecated module attribute and emit a ``DeprecationWarning``.

    Handles old capitalization (``Vector3D``), flattened nested messages
    (``MovingObjectVehicleAttributes``) and ``EnumWrapper``. Returns
    :data:`MISSING` if ``name`` is none of these.

    The default ``stacklevel`` points the warning at the code that accessed the
    attribute, when called directly from a module ``__getattr__``.
    """
    for alias_map in (capitalization_map, nested_messages_map):
        if name in alias_map:
            canonical, target = alias_map[name]
            _warnings.warn(
                f"'{name}' is deprecated. Use '{canonical}' instead.",
                DeprecationWarning,
                stacklevel=stacklevel,
            )
            return target
    if name == "EnumWrapper":
        _warnings.warn(
            "'EnumWrapper' is deprecated.", DeprecationWarning, stacklevel=stacklevel
        )
        return EnumWrapper
    return MISSING


def deprecated_names(capitalization_map: dict, nested_messages_map: dict) -> set:
    """Names that :func:`resolve_deprecated_name` resolves, for ``__dir__``."""
    return set(capitalization_map) | set(nested_messages_map) | {"EnumWrapper"}


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

    # 1. Enums wrapped in EnumWrapper and patched for TYPE_*/SUBTYPE_*
    all_enums = {}
    for name in getattr(generated_module, "__all__", []):
        cls = getattr(generated_module, name)
        if isinstance(cls, type):
            if issubclass(cls, _ProtobufMessage):
                all_enums.update(_find_enums(cls, name))
            elif issubclass(cls, _ProtobufEnum):
                all_enums[name] = cls

    for n, e in all_enums.items():
        _patch_enum(e)
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
        target = resolve_deprecated_name(name, capitalization_map, nested_messages_map)
        if target is not MISSING:
            return target
        if existing_getattr is not None:
            return existing_getattr(name)
        raise AttributeError(f"module '{module_name}' has no attribute '{name}'")

    existing_dir = module_globals.get("__dir__")

    def __dir__():
        base = list(module_globals.keys())
        if existing_dir is not None:
            base = existing_dir()
        return sorted(
            set(base) | deprecated_names(capitalization_map, nested_messages_map)
        )

    module_globals["__getattr__"] = __getattr__
    module_globals["__dir__"] = __dir__

    return capitalization_map, nested_messages_map


setup = setup_deprecation


class _CallableModule(_types.ModuleType):
    def __call__(self, *args, **kwargs):
        return setup_deprecation(*args, **kwargs)


_sys.modules[__name__].__class__ = _CallableModule
