from .generated.google.protobuf import *  # noqa: F403
from .generated.osi3 import *  # noqa: F403
from .io import Writer, read, MESSAGES_TYPE  # noqa: F401
from . import generated


for c_name in generated.osi3.__all__:
    c = getattr(generated.osi3, c_name)
    if hasattr(c, "parse"):
        c.ParseFromString = c.parse
