import struct
from pathlib import Path
from typing import Any

from mcap_protobuf.decoder import DecoderFactory
from mcap.reader import make_reader
from mcap_protobuf.writer import Writer as McapWriter

from . import osi3trace
from .generated import osi3

MESSAGES_TYPE = [
    "SensorView",
    "SensorViewConfiguration",
    "GroundTruth",
    "HostVehicleData",
    "SensorData",
    "TrafficCommand",
    "TrafficCommandUpdate",
    "TrafficUpdate",
    "MotionRequest",
    "StreamingUpdate",
    "MapAsamOpenDrive"
]

def gen2betterosi(schema, message, return_sensor_view=False, return_ground_truth=False, passthrough=False):
    if not passthrough:
        if any(schema.name == f'osi3.{k}' for k in MESSAGES_TYPE):
            message_cls = getattr(osi3, schema.name.split('.')[-1])
            message = message_cls().parse(message.SerializeToString())
        else:
            return None
    if not return_sensor_view and not return_ground_truth:
        return message
    if return_sensor_view and schema.name == 'osi3.SensorView':
        return message
    if return_ground_truth:
        if schema.name == 'osi3.SensorView':
            return message.global_ground_truth
        if schema.name == 'osi3.GroundTruth':
            return message                        
    return None
    
    
def read(filepath: str, return_sensor_view=False, return_ground_truth=False, mcap_return_betterosi: bool = True, mcap_topics: list|None = None, osi_message_type: str|None = None) -> list[Any]:
    p = Path(filepath)
    if p.suffix=='.mcap':
        with p.open("rb") as f:
            reader = make_reader(f, decoder_factories=[DecoderFactory()])
            views = (gen2betterosi(schema, proto_msg, return_sensor_view=return_sensor_view, return_ground_truth=return_ground_truth, passthrough=not mcap_return_betterosi) for schema, channel, message, proto_msg in reader.iter_decoded_messages(topics=mcap_topics))
            views = (v for v in views if v is not None)
            for view in views:
                yield view
    elif p.suffix=='.osi':
        if return_sensor_view or return_ground_truth:
            try:
                next(iter(osi3trace.OSITrace(str(filepath), 'SensorView')))
                is_sv = True
            except RuntimeError as e:
                if return_sensor_view:
                    raise e
                is_sv = False
            if is_sv:
                views = osi3trace.OSITrace(str(filepath), 'SensorView')
                if not return_sensor_view:
                    views = (m.global_ground_truth for m in views)
            else:
                views = osi3trace.OSITrace(str(filepath), 'GroundTruth')
        else:
            if osi_message_type is None:
                raise ValueError('Specify the osi_message_type, e.g., `GroundTruth`.')
            views =  osi3trace.OSITrace(str(filepath), osi_message_type)
        for view in views:
            yield view
    else:
        raise NotImplementedError()



class Writer():
    def __init__(self, output, topic='ground_truth', mode='wb', **kwargs):
        p = Path(output)
        if p.suffix=='.mcap':
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

    def add(self, view, topic:str=None, log_time=None):
        if self.write_mcap:
            if log_time is None:
                log_time = int(view.timestamp.nanos+view.timestamp.seconds*1e9)
            topic = self.topic if topic is None else topic
            self.mcap_writer.write_message(topic, view, 
                log_time=log_time, publish_time=log_time),
        if self.write_osi:
            buffer = bytes(view)
            self.file.write(struct.pack("<L", len(buffer)))
            self.file.write(buffer)

    def __exit__(self, exc_: Any, exc_type_: Any, tb_: Any):
        if self.write_mcap:
            self.mcap_writer.finish()
        self.file.close()