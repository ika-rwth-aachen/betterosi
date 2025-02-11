import base64
import json
from dataclasses import dataclass
from typing import Any


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

@dataclass  
class Descriptor():
    full_name: str
    file: File
        
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
    
    @staticmethod
    def create_descriptor_json(filepath: str = 'descriptors.json'):
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
        ) for o in [osi3.SensorView, osi3.GroundTruth]}

        with open(filepath, 'w') as f:
            json.dump(osi3_descriptors, f)
                

