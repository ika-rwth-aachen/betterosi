from pathlib import Path

from betterosi.descriptor import Descriptor
from betterosi.io import Writer, read_ground_truth  # noqa: F401

from . import generated
from .generated.osi3 import *  # noqa: F403
from .generated.osi3 import GroundTruth, SensorView

descriptors = Descriptor.create_descriptors_from_json(Path(__file__).parent/'descriptors.json')
SensorView.DESCRIPTOR = descriptors['osi3.SensorView']
GroundTruth.DESCRIPTOR =  descriptors['osi3.GroundTruth']
    
for c_name in generated.osi3.__all__:
    c = getattr(generated.osi3, c_name)
    if hasattr(c, 'parse'):
        c.ParseFromString = c.parse
