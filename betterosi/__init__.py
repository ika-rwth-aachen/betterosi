from betterosi.io import Writer, read, MESSAGES_TYPE  # noqa: F401
from google.protobuf.descriptor_pb2 import EnumDescriptorProto, DescriptorProto, FileDescriptorProto
from . import generated
from .generated.osi3 import *  # noqa: F403
from enum import EnumType
from google.protobuf.descriptor_pool import DescriptorPool


for c_name in generated.osi3.__all__:
    c = getattr(generated.osi3, c_name)
    if hasattr(c, 'parse'):
        c.ParseFromString = c.parse


def get_proto_dependencies(obj):
    if hasattr(obj, '_betterproto'):
        return set([o for os in [[v]+list(get_proto_dependencies(v)) for v in obj._betterproto.cls_by_field.values() if hasattr(v, '_serialized_pb')] for o in os])
    else:
        return []

def insert_into_hierarchy_dict(d, name, cls):
    first = name.split('.')[0]
    if first not in d:
        d[first] = {'cls': None,  'children': {}}
    if len(name.split('.'))>1:
        insert_into_hierarchy_dict(d[first]['children'], '.'.join(name.split('.')[1:]), cls)
    else:
        d[first]['cls'] = cls


def cls_to_proto(message, children):
    if isinstance(message, EnumType):
        proto = EnumDescriptorProto()
        proto.ParseFromString(message._serialized_pb())
        proto.name = proto.name.split('.')[-1]
        return None, proto
    else:
        proto = DescriptorProto()
        proto.ParseFromString(message._serialized_pb())
        proto.name = proto.name.split('.')[-1]
        proto.ClearField("enum_type")  # Remove all enums first
        proto.ClearField("nested_type")  # Remove all enums first
        for k, v in children.items():
            m, e = cls_to_proto(v['cls'], v['children'])
            if m is not None:
                proto.nested_type.add().MergeFrom(m)
            if e is not None:
                proto.enum_type.add().MergeFrom(e)
        return proto, None

def get_descriptor(cls, package='osi3'):
    fd = FileDescriptorProto(name=cls.__name__, package=package)
    
    package_hierarchy = {} 
    for o in list(get_proto_dependencies(cls))+[cls]:
        proto = DescriptorProto()
        proto.ParseFromString(o._serialized_pb())
        insert_into_hierarchy_dict(package_hierarchy, proto.name, o)
        
    messages = []
    enums = []
    for k, v in package_hierarchy.items():
        m,e = cls_to_proto(v['cls'], v['children'])
        if m is not None:
            messages.append(m)
        if e is not None:
            enums.append(e)
    fd = FileDescriptorProto(name=cls.__name__, package=package)
    fd.message_type.extend(messages)
    fd.enum_type.extend(enums)
    pool = DescriptorPool()
    pool.Add(fd)

    return pool.FindMessageTypeByName(f'{package}.{cls.__name__}')

for c_name in MESSAGES_TYPE:
    o = getattr(generated.osi3, c_name)
    setattr(o, 'DESCRIPTOR', get_descriptor(o))
