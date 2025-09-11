from .generated.google.protobuf import *  # noqa: F403
from .generated.osi3 import *  # noqa: F403
from .io import Writer, read, MESSAGES_TYPE  # noqa: F401
from . import generated
from .generated import osi3 as osi
import betterproto2


class EnumWrapper:
    def __init__(self, cls):
        self.wrapped = cls

    def __repr__(self):
        return f"EnumWrapper of {repr(self.wrapped)}"

    def __getattr__(self, name):
        try:
            return getattr(self.wrapped, name)
        except AttributeError as e:
            n = self.wrapped.betterproto_renamed_proto_names_to_value().get(name, None)
            if n is None:
                raise e
            else:
                return self.wrapped(n)

    def from_string(self, name):
        try:
            return self.wrapped.from_string(name)
        except ValueError as e:
            n = self.wrapped.betterproto_renamed_proto_names_to_value().get(name, None)
            if n is None:
                raise e
            else:
                return self.wrapped(n)

    def __iter__(self):
        return iter(self.wrapped)

    def __call__(self, val):
        return self.wrapped(val)


enums = {
    o: getattr(osi, o)
    for o in osi.__all__
    if isinstance(getattr(osi, o), betterproto2.enum_._EnumMeta)
}

for n, e in enums.items():
    globals()[n] = EnumWrapper(e)

for c_name in generated.osi3.__all__:
    c = getattr(generated.osi3, c_name)
    if hasattr(c, "parse"):
        c.ParseFromString = c.parse
