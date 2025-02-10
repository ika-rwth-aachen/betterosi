import importlib
from .generated.osi3 import *  # noqa: F403
from pathlib import Path
from .generated.osi3 import GroundTruth, SensorView
import struct
from .osi3trace import OSITrace
from . import generated
from typing import Any
from mcap.reader import make_reader
from mcap_protobuf.reader import read_protobuf_messages 
from mcap_protobuf.writer import Writer as McapWriter

OSI_NOT_INSTALLED_STRING = 'install osi'
MCAP_NOT_INSTALLED_STRING = 'install mcap'

class RaiseOSINotInstalledDescriptor():
    def __getattribute__(self, k):
        raise RuntimeError(OSI_NOT_INSTALLED_STRING)
osi3_installed = importlib.util.find_spec('osi3') is not None  
if osi3_installed:
    import osi3
    SensorView.DESCRIPTOR = osi3.osi_sensorview_pb2.DESCRIPTOR
    GroundTruth.DESCRIPTOR = osi3.osi_groundtruth_pb2.GroundTruth.DESCRIPTOR
else:
    SensorView.DESCRIPTOR = RaiseOSINotInstalledDescriptor()
    GroundTruth.DESCRIPTOR = RaiseOSINotInstalledDescriptor()
    
for c_name in generated.osi3.__all__:
    c = getattr(generated.osi3, c_name)
    if hasattr(c, 'parse'):
        c.ParseFromString = c.parse



       
def read_ground_truth(filepath: str, mcap_return_betterosi: bool = True, mcap_topics: list|None = None) -> list[GroundTruth]:
    # reads osi or mcap SensorViews or GroundTruth
    p = Path(filepath)
    if p.suffix=='.mcap':
        if mcap_return_betterosi:
                try:
                    with p.open("rb") as f:
                        reader = make_reader(f)
                        views = [SensorView().parse(message.data) for schema, channel, message in reader.iter_messages(topics=mcap_topics) if schema.name == "osi3.SensorView"]
                    if len(views)==0:
                        raise RuntimeError()
                except RuntimeError:
                    with p.open("rb") as f:
                        reader = make_reader(f)
                        views = [GroundTruth().parse(message.data) for schema, channel, message in reader.iter_messages(topics=mcap_topics) if schema.name == "osi3.GroundTruth"]
        else:
            views = [m.proto_msg for m in read_protobuf_messages(filepath) if m.proto_msg.__name__ in ['SensorView', 'GroundTruth']]
            if hasattr(views[0], 'global_ground_truth'):
                views = [v.global_ground_truth for v in views]
            
    elif p.suffix=='.osi':
        if osi3_installed:
            try:
                views = [m.global_ground_truth for m in OSITrace(str(filepath), 'SensorView')]
            except Exception:
                views = [m for m in OSITrace(filepath, 'GroundTruth')]
        else:
            raise RuntimeError(OSI_NOT_INSTALLED_STRING)
    else:
        raise NotImplementedError()
    return views

class Writer():
    def __init__(self, output, topic='ConvertedTrace', mode='wb', **kwargs):
        p = Path(output)
        if p.suffix=='.mcap':
            if not osi3_installed:
                raise RuntimeError(OSI_NOT_INSTALLED_STRING)
            self.write_mcap = True
            self.write_osi = False
            self.topic = topic
            self.file = open(p, mode)
            self.mcap_writer = McapWriter(self.file, **kwargs)
        elif p.suffix=='.osi':
            self.write_mcap = False
            self.write_osi = True
            self.file = open(p, mode)
        else:
            raise NotImplementedError()
        
    def __enter__(self):
        return self

    def add(self, gt: GroundTruth):
        if self.write_mcap:
            log_time = int(gt.timestamp.nanos+gt.timestamp.seconds*1e9)
            self.mcap_writer.write_message(self.topic, gt, 
                log_time=log_time, publish_time=log_time),

        if self.write_osi:
            buffer = bytes(gt)
            self.file.write(struct.pack("<L", len(buffer)))
            self.file.write(buffer)

    def __exit__(self, exc_: Any, exc_type_: Any, tb_: Any):
        if self.write_mcap:
            self.mcap_writer.finish()
        self.file.close()