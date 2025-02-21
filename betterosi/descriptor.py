import base64
import json
from dataclasses import dataclass
from typing import Any
import typer
from pathlib import Path
import importlib
import sys

app = typer.Typer()

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

class Dependency():
    def __init__(self, name):
        super().__init__()
        self.name = name
        
@dataclass    
class File():
    name: str
    serialized_pb: Any
    dependencies: list["File"]
    
    def CopyToProto(self, proto):
        return proto.ParseFromString(self.serialized_pb)
    
def get_module(k, input_dir):
    spec = importlib.util.spec_from_file_location("k", input_dir/f'osi_{k.lower()}_pb2.py')
    foo = importlib.util.module_from_spec(spec)
    sys.modules["k"] = foo
    spec.loader.exec_module(foo)
    return foo

def relsolve_dependencies(filedescriptor):
    return dict(
    name = filedescriptor.name,
    serialized_pb_base64 = base64.b64encode(filedescriptor.serialized_pb).decode(),
    dependencies = [relsolve_dependencies(d) for d in filedescriptor.dependencies]
    )
            
@dataclass  
class Descriptor():
    full_name: str
    file: File
    
    @classmethod
    def get_osi_classe_names(cls):
        return MESSAGES_TYPE
    
    @classmethod
    def create_descriptors_from_json(cls, filepath: str ='descriptors.json'):
        with open(filepath, 'r') as f:
            osi3_descriptors = json.load(f)
        result = {}
        def parse_file(file_dict):
            return File(
                name = file_dict['name'],
                serialized_pb = base64.b64decode(file_dict['serialized_pb_base64'].encode()),
                dependencies = [parse_file(o) for o in file_dict['dependencies']]
            )
        for k, v in osi3_descriptors.items():
            result[k] = cls(full_name=v['full_name'], 
                                file=parse_file(v))
        return result
    
    @classmethod
    def set_descriptors(cls):
        import betterosi
        descriptors = Descriptor.create_descriptors_from_json(Path(__file__).parent/'descriptors.json')
        for c_name in cls.get_osi_classe_names():
            setattr(getattr(betterosi, c_name), 'DESCRIPTOR', descriptors[f'osi3.{c_name}'])
    
    @classmethod
    def create_descriptor_json(cls, filepath: str = 'betterosi/descriptors.json'):
        import osi3
        def relsolve_dependencies(filedescriptor):
            return dict(
                name = filedescriptor.name,
                serialized_pb_base64 = base64.b64encode(filedescriptor.serialized_pb).decode(),
                dependencies = [relsolve_dependencies(d) for d in filedescriptor.dependencies]
            )
        osi3_descriptors = {o.DESCRIPTOR.full_name: dict(   
            full_name = o.DESCRIPTOR.full_name,
            name = o.DESCRIPTOR.file.name,
            serialized_pb_base64 = base64.b64encode(o.DESCRIPTOR.file.serialized_pb).decode(),
            dependencies = [relsolve_dependencies(d) for d in o.DESCRIPTOR.file.dependencies]
        ) for o in [getattr(getattr(osi3, f'osi_{k.lower()}_pb2'), k) for k in cls.get_osi_classe_names()]}
        with open(filepath, 'w') as f:
            json.dump(osi3_descriptors, f)
    
    @classmethod  
    def create_descriptor_json2(cls, filepath: str = 'betterosi/descriptors2.json', input_dir='.'):
        input_dir = Path(input_dir).absolute()


        osi3_descriptors = {f'osi3.{k}': dict(   
            full_name = f'osi3.{k}',
            name = o.DESCRIPTOR.name,
            serialized_pb_base64 = base64.b64encode(o.DESCRIPTOR.serialized_pb).decode(),
            dependencies = [relsolve_dependencies(d) for d in o.DESCRIPTOR.dependencies]
        ) for k, o in [(k, get_module(k, input_dir)) for k in cls.get_osi_classe_names()]}
        with open(filepath, 'w') as f:
            json.dump(osi3_descriptors, f)
            
            
@app.command()            
def main(filepath: str = 'betterosi/descriptors.json'):
    Descriptor.create_descriptor_json2(filepath)
    
if __name__ == "__main__":
    app()