# betterosi - a python library for reading and writing open-simulation-interface files using betterproto2

[![](https://img.shields.io/badge/license-MPL%202.0-blue.svg)](https://github.com/ika-rwth-aachen/betterosi/blob/master/LICENSE) 
[![](https://img.shields.io/pypi/v/betterosi.svg)](https://pypi.python.org/pypi/betterosi)
[![](https://github.com/ika-rwth-aachen/betterosi/workflows/CI/badge.svg)](https://github.com/ika-rwth-aachen/betterosi/actions)
[![](https://img.shields.io/pypi/pyversions/betterosi.svg)](https://pypi.python.org/pypi/betterosi/)
[![](https://img.shields.io/github/issues-raw/ika-rwth-aachen/betterosi.svg)](https://github.com/ika-rwth-aachen/betterosi/issues)

A python library for reading and writing [ASAM OSI (Open-Simulation-Interace)](https://github.com/OpenSimulationInterface/open-simulation-interface) files (either `.osi` binary traces or [MCAP](https://github.com/foxglove/mcap) files) using [betterproto2](https://github.com/betterproto/python-betterproto2) instead of the default protobuf generated code (better typing and enum support).

- Supports writing and reading either mcap or osi files with `betterosi.Writer` and `betterosi.read`.
- View OSI or MCAP file containing OSI GroundTruth `betterosi-viewer <filepath.mcap / filepath.osi>`(adapted from [esmini](https://github.com/esmini/esmini))
- Convert osi to mcap with `betterosi-to-mcap <filepath to osi>`.

The library uses code from [esmini](https://github.com/esmini/esmini) (`betterosi/viewer.py`) under MPL 2.0 license and the code from [open-simulation-interface](https://github.com/OpenSimulationInterface/open-simulation-interface) to read osi traces (`betterosi/osi3trace.py`).

The library uses code generation of [python-betterproto2-compiler](https://github.com/betterproto/python-betterproto2-compiler) to generate python code from the protobuf definitions of [open-simulation-interface](https://github.com/OpenSimulationInterface/open-simulation-interface).

Since OSI and esmini are under MPL, also this repository is published under MPL-2.0 license.

## Differences to OSI 3.7.0
The proto definitions extend the OSI 3.7.0 definitions in the following ways:
- Add `MapAsamOpenDrive` Message: Packages the XML content of an ASAM OpenDRIVE map in a proto Message

See [omega-prime](https://github.com/ika-rwth-aachen/omega-prime) for details.

## Install

`pip install betterosi`
## Create an OSI or MCAP trace

To create an OSI or MCAP trace, you need to use `betterosi.Writer`. After creating the OSI Message of your desire, just add it to the `Writer` as shown in the examples below for either MCAP traaces or OSI traces. 


<!--pytest.mark.skip-->
```python
import betterosi

with betterosi.Writer('test.mcap') as writer:
    gt = betterosi.GroundTruth(...)
    writer.add(gt)

with betterosi.Writer('test.osi') as writer:
    sv = betterosi.SensorView(...)
    writer.add(sv)
```

Below a full example is given which creates three files, and MCAP trace and and OSI trace with GroundTruth messages and a MCAP trace of SensorViews. If you use the code, you obviously just need one of the writers.

```python
import betterosi
NANOS_PER_SEC = 1_000_000_000


with betterosi.Writer('test.mcap') as writer_mcap, betterosi.Writer('test.osi') as writer_osi, betterosi.Writer('test_sv.mcap') as writer_sv:
    moving_object = betterosi.MovingObject(id=betterosi.Identifier(value=42),
        type = betterosi.MovingObjectType.UNKNOWN,
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
    sv = betterosi.SensorView(
        version=betterosi.InterfaceVersion(version_major= 3, version_minor=7, version_patch=0),
        timestamp=betterosi.Timestamp(seconds=0, nanos=0),
        global_ground_truth=gt,
        host_vehicle_id=betterosi.Identifier(value=0)
    )
    # Generate 1000 OSI messages for a duration of 10 seconds
    for i in range(1000):
        total_nanos = i*0.01*NANOS_PER_SEC
        gt.timestamp.seconds = int(total_nanos // NANOS_PER_SEC)
        gt.timestamp.nanos = int(total_nanos % NANOS_PER_SEC)
        moving_object.base.position.x += 0.5
        sv.timestamp = gt.timestamp

        writer_mcap.add(gt)
        writer_osi.add(gt)
        writer_sv.add(sv)
```

When writing MCAP messages you can specifiy the topic in the writer and the add function by setting the `topic` argument. When reading such files, set the argument `mcap_topic` to the same string.

## Read OSI and MCAP
With `betterosi.read` you can read an mcap or osi trace. `read` returns a generator. With the following code, you can get a list of the GroundTruth messages from a trace, even if the GroundTruth are nested inside SensorViews. It works the same for OSI traces.

```python
import betterosi
ground_truths = list(betterosi.read('test_sv.mcap', return_ground_truth=True))
print([len(ground_truths), ground_truths[0]])
```
Above code prints the following:
<!--pytest-codeblocks:expected-output-->
```
[1000, GroundTruth(version=InterfaceVersion(version_major=3, version_minor=7), timestamp=Timestamp(), host_vehicle_id=Identifier(), moving_object=[MovingObject(id=Identifier(value=42), base=BaseMoving(dimension=Dimension3D(length=5.0, width=2.0, height=1.0), position=Vector3D(x=0.5), orientation=Orientation3D(), velocity=Vector3D(x=1.0)))])]
```

If you want a list of the sensor views directly:

```python
import betterosi
sensor_views = betterosi.read('test_sv.mcap', return_sensor_view=True)
print(next(sensor_views))
```
The above prints:
<!--pytest-codeblocks:expected-output-->
```
SensorView(version=InterfaceVersion(version_major=3, version_minor=7), timestamp=Timestamp(), global_ground_truth=GroundTruth(version=InterfaceVersion(version_major=3, version_minor=7), timestamp=Timestamp(), host_vehicle_id=Identifier(), moving_object=[MovingObject(id=Identifier(value=42), base=BaseMoving(dimension=Dimension3D(length=5.0, width=2.0, height=1.0), position=Vector3D(x=0.5), orientation=Orientation3D(), velocity=Vector3D(x=1.0)))]), host_vehicle_id=Identifier())
```
If you want to read any OSI trace, you just need to give the filename.
```python
import betterosi
any_osi_message = betterosi.read('test.osi')
any_osi_message = betterosi.read('test.mcap')
```


# Generate library code

```
pip install grpcio-tools betterproto2_compiler


python gen_protos.py
```

cd into osi-proto and run the following command to generate the code

```
cd osi-proto

mkdir ../betterosi/generated

python -m grpc_tools.protoc -I . --python_betterproto2_out=../betterosi/generated --python_betterproto2_opt=google_protobuf_descriptors osi_common.proto osi_datarecording.proto osi_detectedlane.proto osi_detectedobject.proto osi_detectedoccupant.proto osi_detectedroadmarking.proto osi_detectedtrafficlight.proto osi_detectedtrafficsign.proto osi_environment.proto osi_featuredata.proto osi_groundtruth.proto osi_hostvehicledata.proto osi_lane.proto osi_logicaldetectiondata.proto osi_logicallane.proto osi_motionrequest.proto osi_object.proto osi_occupant.proto osi_referenceline.proto osi_roadmarking.proto osi_route.proto osi_sensordata.proto osi_sensorspecific.proto osi_sensorview.proto osi_sensorviewconfiguration.proto osi_streamingupdate.proto osi_trafficcommand.proto osi_trafficcommandupdate.proto osi_trafficlight.proto osi_trafficsign.proto osi_trafficupdate.proto osi_version.proto osi_mapasamopendrive.proto
```

# LICENSE and Copyright
This code is published under MPL-2.0 license.
It utilizes and modifies parts of [esmini](https://github.com/esmini/esmini) ([betterosi/viewer.py](betterosi/viewer.py)) under MPL-2.0 and [open-simulation-interface](https://github.com/OpenSimulationInterface/open-simulation-interface) [osi-proto/*](osi-proto/) under MPL-2.0.

# Acknowledgements

This package is developed as part of the [SYNERGIES project](https://synergies-ccam.eu).

<img src="https://raw.githubusercontent.com/ika-rwth-aachen/betterosi/refs/heads/main/synergies.svg"
style="width:2in" />



Funded by the European Union. Views and opinions expressed are however those of the author(s) only and do not necessarily reflect those of the European Union or European Climate, Infrastructure and Environment Executive Agency (CINEA). Neither the European Union nor the granting authority can be held responsible for them. 

<img src="https://raw.githubusercontent.com/ika-rwth-aachen/betterosi/refs/heads/main/funded_by_eu.svg"
style="width:4in" />

# Notice

> [!IMPORTANT]
> The project is open-sourced and maintained by the [**Institute for Automotive Engineering (ika) at RWTH Aachen University**](https://www.ika.rwth-aachen.de/).
> We cover a wide variety of research topics within our [*Vehicle Intelligence & Automated Driving*](https://www.ika.rwth-aachen.de/en/competences/fields-of-research/vehicle-intelligence-automated-driving.html) domain.
> If you would like to learn more about how we can support your automated driving or robotics efforts, feel free to reach out to us!
> :email: ***opensource@ika.rwth-aachen.de***