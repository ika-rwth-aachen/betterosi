from warnings import warn
from betterosi.descriptor import Descriptor
from betterosi.io import Writer, read  # noqa: F401

from . import generated
from .generated.osi3 import *  # noqa: F403

#try:
Descriptor.set_descriptors()
#except KeyError:
#    warn('Not all descriptors could be set. Regenerate the descriptors if you want to correctly write mcap files.')
    
for c_name in generated.osi3.__all__:
    c = getattr(generated.osi3, c_name)
    if hasattr(c, 'parse'):
        c.ParseFromString = c.parse
