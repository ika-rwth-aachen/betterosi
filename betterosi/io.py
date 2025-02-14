import struct
from pathlib import Path
from typing import Any

from mcap_protobuf.decoder import DecoderFactory
from mcap.reader import make_reader
from mcap_protobuf.writer import Writer as McapWriter

from betterosi.generated.osi3 import GroundTruth, SensorView
from betterosi.osi3trace import OSITrace


def gen2betterosi(schema, message, use_sv=False, passthrough=False):
    if schema.name == 'osi3.SensorView':
        sv = message if passthrough else SensorView().parse(message.SerializeToString())
        return sv if use_sv else sv.global_ground_truth
    elif not use_sv and schema.name == 'osi3.GroundTruth':
        gt = message if passthrough else GroundTruth().parse(message.SerializeToString())
        return gt
    return None
    
    
def read(filepath: str, return_sensor_view=False, mcap_return_betterosi: bool = True, mcap_topics: list|None = None) -> list[GroundTruth]|list[SensorView]:
    # reads osi or mcap SensorViews or GroundTruth
    p = Path(filepath)
    if p.suffix=='.mcap':
        with p.open("rb") as f:
            reader = make_reader(f, decoder_factories=[DecoderFactory()])
            views = [gen2betterosi(schema, proto_msg, use_sv=False, passthrough=not mcap_return_betterosi) for schema, channel, message, proto_msg in reader.iter_decoded_messages(topics=mcap_topics)]
            views = [v for v in views if v is not None]
    elif p.suffix=='.osi':
        try:
            views = [m for m in OSITrace(str(filepath), 'SensorView')]
            if not return_sensor_view:
                views = [m.global_ground_truth for m in views]
        except Exception as e:
            if return_sensor_view:
                raise e
            views = [m for m in OSITrace(str(filepath), 'GroundTruth')]
    else:
        raise NotImplementedError()
    if len(views)==0:
        raise RuntimeError()
    return views

class Writer():
    def __init__(self, output, topic='ConvertedTrace', mode='wb', **kwargs):
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

    def add(self, view: GroundTruth|SensorView):
        if self.write_mcap:
            log_time = int(view.timestamp.nanos+view.timestamp.seconds*1e9)
            self.mcap_writer.write_message(self.topic, view, 
                log_time=log_time, publish_time=log_time),
        if self.write_osi:
            buffer = bytes(view)
            self.file.write(struct.pack("<L", len(buffer)))
            self.file.write(buffer)

    def __exit__(self, exc_: Any, exc_type_: Any, tb_: Any):
        if self.write_mcap:
            self.mcap_writer.finish()
        self.file.close()