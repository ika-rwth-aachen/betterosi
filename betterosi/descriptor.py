import base64
import json
from dataclasses import dataclass
from typing import Any
import typer
import betterosi
from pathlib import Path

app = typer.Typer()

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
    def get_osi_classe_names(cls):
        return list(betterosi.osi3trace.MESSAGES_TYPE.keys())
    
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
            
@app.command()            
def main(filepath: str = 'betterosi/descriptors.json'):
    Descriptor.create_descriptor_json(filepath)
    
if __name__ == "__main__":
    app()