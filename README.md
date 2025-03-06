# betterosi - a python library for reading and writing open-simulation-interface files using betterproto2

A python library for reading and writing [ASAM OSI (Open-Simulation-Interace)](https://github.com/OpenSimulationInterface/open-simulation-interface) files (either `.osi` binary traces or [MCAP](https://github.com/foxglove/mcap) files) using [betterproto2](https://github.com/betterproto/python-betterproto2) instead of the default protobuf generated code (better typing and enum support).

- Supports writing and reading either mcap or osi files with `betterosi.Writer` and `betterosi.read`.
- View OSI or MCAP file containing OSI GroundTruth `betterosi-viewer <filepath.mcap / filepath.osi>`(adapted from [esmini](https://github.com/esmini/esmini))
- Convert osi to mcap with `betterosi-to-mcap <filepath to osi>`.

The library uses code from [esmini](https://github.com/esmini/esmini) (`betterosi/viewer.py`) under MPL 2.0 license and the code from [open-simulation-interface](https://github.com/OpenSimulationInterface/open-simulation-interface) to read osi traces (`betterosi/osi3trace.py`).

The library uses code generation of [python-betterproto2-compiler](https://github.com/betterproto/python-betterproto2-compiler) to generate python code from the protobuf definitions of [open-simulation-interface](https://github.com/OpenSimulationInterface/open-simulation-interface).

Since OSI and esmini are under MPL, also this repository is published under MPL-2.0 license.

## Install

`pip install betterosi`

## Read OSI and MCAP
The following code creates a list of GroundTruth messages from an MCAP file for OSI trace containing SensorViews or GroundTruth messages.
```python
import betterosi

ground_truths = betterosi.read('filepath.mcap/filepath.osi', return_ground_truth=True)
sensor_views = betterosi.read('filepath.osi', return_sensor_view=True)
any_osi_message = betterosi.read('filepath.mcap')

```
## Writing MCAP file
With the following code you can create an MCAP file. If you change the filepath `test.mcap` to `test.osi`, an OSI tracefile will be created.

### Create MCAP

```python
with betterosi.Writer(f'test.mcap') as writer:
    gt = betterosi.GroundTruth(...)
    writer.add(gt)
```

### Create OSI
```python
with betterosi.Writer(f'test.osi') as writer:
    sv = betterosi.SensorView(...)
    writer.add(sv)
```

### Full example

```python
import betterosi
NANOS_PER_SEC = 1_000_000_000


with betterosi.Writer(f'test.mcap') as writer:
    moving_object = betterosi.MovingObject(id=betterosi.Identifier(value=42),
        type = betterosi.MovingObjectType.TYPE_UNKNOWN,
        base=betterosi.BaseMoving(
            dimension= betterosi.Dimension3D(length=5, width=2, height=1),
            position = betterosi.Vector3D(x=0, y=0, z=0),
            orientation = betterosi.Orientation3D(roll = 0.0, pitch = 0.0, yaw = 0.0),
            velocity = betterosi.Vector3D(x=1, y=0, z=0)
    ))
    gt = betterosi.GroundTruth(
        version=betterosi.InterfaceVersion(version_major= 3, version_minor=7, version_patch=0),
        timestamp=betterosi.Timestamp(seconds=0, nanos=0),
        moving_object=[
            moving_object
        ],
        host_vehicle_id=betterosi.Identifier(value=0)
    )
    # Generate 1000 OSI messages for a duration of 10 seconds
    for i in range(1000):
        total_nanos = i*0.01*NANOS_PER_SEC
        gt.timestamp.seconds = int(total_nanos // NANOS_PER_SEC)
        gt.timestamp.nanos = int(total_nanos % NANOS_PER_SEC)
        moving_object.base.position.x += 0.5

        writer.add(gt)
```


# Generate library code

```
pip install grpcio-tools git+https://github.com/MichaelSchuldes/python-betterproto2-compiler@serialized_descriptors
```

cd into osi-proto and run the following command to generate the code 

```
cd osi-proto

mkdir ../betterosi/generated

python -m grpc_tools.protoc -I . --python_betterproto2_out=../betterosi/generated osi_common.proto osi_datarecording.proto osi_detectedlane.proto osi_detectedobject.proto osi_detectedoccupant.proto osi_detectedroadmarking.proto osi_detectedtrafficlight.proto osi_detectedtrafficsign.proto osi_environment.proto osi_featuredata.proto osi_groundtruth.proto osi_hostvehicledata.proto osi_lane.proto osi_logicaldetectiondata.proto osi_logicallane.proto osi_motionrequest.proto osi_object.proto osi_occupant.proto osi_referenceline.proto osi_roadmarking.proto osi_route.proto osi_sensordata.proto osi_sensorspecific.proto osi_sensorview.proto osi_sensorviewconfiguration.proto osi_streamingupdate.proto osi_trafficcommand.proto osi_trafficcommandupdate.proto osi_trafficlight.proto osi_trafficsign.proto osi_trafficupdate.proto osi_version.proto osi_mapasamopendrive.proto
```

# LICENSE and Copyright
This code is published under MPL-2.0 license. 
It utilizes and modifies parts of [esmini](https://github.com/esmini/esmini) ([betterosi/viewer.py](betterosi/viewer.py)) under MPL-2.0 and [open-simulation-interface](https://github.com/OpenSimulationInterface/open-simulation-interface) ([osi-proto/*](osi-proto/) and [betterosi/osi3trace.py](betterosi/osi3trace.py)) under MPL-2.o