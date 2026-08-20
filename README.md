# betterosi - a python library for reading and writing open-simulation-interface files

[![](https://img.shields.io/badge/license-MPL%202.0-blue.svg)](https://github.com/ika-rwth-aachen/betterosi/blob/master/LICENSE) 
[![](https://img.shields.io/pypi/v/betterosi.svg)](https://pypi.python.org/pypi/betterosi)
[![](https://github.com/ika-rwth-aachen/betterosi/workflows/CI/badge.svg)](https://github.com/ika-rwth-aachen/betterosi/actions)
[![](https://img.shields.io/pypi/pyversions/betterosi.svg)](https://pypi.python.org/pypi/betterosi/)
[![](https://img.shields.io/github/issues-raw/ika-rwth-aachen/betterosi.svg)](https://github.com/ika-rwth-aachen/betterosi/issues)

<img src="https://github.com/ika-rwth-aachen/betterosi/blob/main/betterosi.svg?raw=True">

A python library for reading and writing [ASAM OSI (Open-Simulation-Interace)](https://github.com/OpenSimulationInterface/open-simulation-interface) files (either `.osi` binary traces or [MCAP](https://github.com/foxglove/mcap) files) using [protobuf-py](https://github.com/bufbuild/protobuf-py) for typed, ergonomic protobuf message classes.

- Supports writing and reading either mcap or osi files with `betterosi.Writer` and `betterosi.read`.
- View OSI or MCAP file containing OSI GroundTruth `betterosi-viewer <filepath.mcap / filepath.osi>`(adapted from [esmini](https://github.com/esmini/esmini))
- Convert osi to mcap with `betterosi-to-mcap <filepath to osi>`.

The library uses code from [esmini](https://github.com/esmini/esmini) (`betterosi/viewer.py`) under MPL 2.0 license and the code from [open-simulation-interface](https://github.com/OpenSimulationInterface/open-simulation-interface) to read osi traces (`betterosi/osi3trace.py`).

The library uses [buf](https://buf.build/) with [protoc-gen-py](https://github.com/bufbuild/protobuf-py) to generate typed Python code from the protobuf definitions of [open-simulation-interface](https://github.com/OpenSimulationInterface/open-simulation-interface).

Since OSI and esmini are under MPL, also this repository is published under MPL-2.0 license.

## OSI Version Support

`betterosi` supports multiple ASAM OSI versions simultaneously (currently `3.7.0` and `3.8.0`).

By default, OSI `3.8.0` is used:
<!--pytest.mark.skip-->
```python
import betterosi

gt = betterosi.GroundTruth(...)
```

To target a specific OSI version, import the corresponding version namespace:
<!--pytest.mark.skip-->
```python
from betterosi import v3_7_0 as betterosi  # uses OSI 3.7.0
```
or
<!--pytest.mark.skip-->
```python
from betterosi import v3_8_0 as betterosi  # uses OSI 3.8.0
```

## Differences to Standard OSI
The proto definitions extend standard OSI definitions in the following ways:
- Add `MapAsamOpenDrive` Message: Packages the XML content of an ASAM OpenDRIVE map in a proto Message

See [omega-prime](https://github.com/ika-rwth-aachen/omega-prime) for details.

## Install

`pip install betterosi`
## Create an OSI or MCAP trace

To create an OSI or MCAP trace, you need to use `betterosi.Writer`. After creating the OSI Message of your desire, just add it to the `Writer` as shown in the examples below for either MCAP traaces or OSI traces. 


<!--pytest.mark.skip-->
```python
import betterosi

with betterosi.Writer("test.mcap") as writer:
    gt = betterosi.GroundTruth(...)
    writer.add(gt)

with betterosi.Writer("test.osi") as writer:
    sv = betterosi.SensorView(...)
    writer.add(sv)
```

Below a full example is given which creates three files, and MCAP trace and and OSI trace with GroundTruth messages and a MCAP trace of SensorViews. If you use the code, you obviously just need one of the writers.

```python
import betterosi

NANOS_PER_SEC = 1_000_000_000


with (
    betterosi.Writer("test.mcap") as writer_mcap,
    betterosi.Writer("test.osi") as writer_osi,
    betterosi.Writer("test_sv.mcap") as writer_sv,
):
    moving_object = betterosi.MovingObject(
        id=betterosi.Identifier(value=42),
        type=betterosi.MovingObjectType.UNKNOWN,
        base=betterosi.BaseMoving(
            dimension=betterosi.Dimension3D(length=5, width=2, height=1),
            position=betterosi.Vector3D(x=0, y=0, z=0),
            orientation=betterosi.Orientation3D(roll=0.0, pitch=0.0, yaw=0.0),
            velocity=betterosi.Vector3D(x=1, y=0, z=0),
        ),
    )
    gt = betterosi.GroundTruth(
        version=betterosi.InterfaceVersion(
            version_major=3, version_minor=7, version_patch=0
        ),
        timestamp=betterosi.Timestamp(seconds=0, nanos=0),
        moving_object=[moving_object],
        host_vehicle_id=betterosi.Identifier(value=0),
    )
    sv = betterosi.SensorView(
        version=betterosi.InterfaceVersion(
            version_major=3, version_minor=7, version_patch=0
        ),
        timestamp=betterosi.Timestamp(seconds=0, nanos=0),
        global_ground_truth=gt,
        host_vehicle_id=betterosi.Identifier(value=0),
    )
    # Generate 1000 OSI messages for a duration of 10 seconds
    for i in range(1000):
        total_nanos = i * 0.01 * NANOS_PER_SEC
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

ground_truths = list(betterosi.read("test_sv.mcap", return_ground_truth=True))
print([len(ground_truths), ground_truths[0]])
```
Above code prints the following:
<!--pytest-codeblocks:expected-output-->
```
[1000, GroundTruth(version=InterfaceVersion(version_major=3, version_minor=7, version_patch=0), timestamp=Timestamp(seconds=0, nanos=0), host_vehicle_id=Identifier(value=0), moving_object=[MovingObject(id=Identifier(value=42), base=BaseMoving(dimension=Dimension3d(length=5.0, width=2.0, height=1.0), position=Vector3d(x=0.5, y=0.0, z=0.0), orientation=Orientation3d(roll=0.0, pitch=0.0, yaw=0.0), velocity=Vector3d(x=1.0, y=0.0, z=0.0)), type=MovingObject.Type.UNKNOWN)])]
```

If you want a list of the sensor views directly:

```python
import betterosi

sensor_views = betterosi.read("test_sv.mcap", return_sensor_view=True)
print(next(sensor_views))
```
The above prints:
<!--pytest-codeblocks:expected-output-->
```
SensorView(version=InterfaceVersion(version_major=3, version_minor=7, version_patch=0), timestamp=Timestamp(seconds=0, nanos=0), global_ground_truth=GroundTruth(version=InterfaceVersion(version_major=3, version_minor=7, version_patch=0), timestamp=Timestamp(seconds=0, nanos=0), host_vehicle_id=Identifier(value=0), moving_object=[MovingObject(id=Identifier(value=42), base=BaseMoving(dimension=Dimension3d(length=5.0, width=2.0, height=1.0), position=Vector3d(x=0.5, y=0.0, z=0.0), orientation=Orientation3d(roll=0.0, pitch=0.0, yaw=0.0), velocity=Vector3d(x=1.0, y=0.0, z=0.0)), type=MovingObject.Type.UNKNOWN)]), host_vehicle_id=Identifier(value=0))
```
If you want to read any OSI trace, you just need to give the filename.
```python
import betterosi

any_osi_message = betterosi.read("test.osi")
any_osi_message = betterosi.read("test.mcap")
```


# Generate library code

```
pip install protoc-gen-py buf-bin

python gen_protos.py
```

Or use `buf generate` directly (requires `buf.yaml` and `buf.gen.yaml` in the project root):

```
buf generate
```

# Name
The library is called betterosi because it was formerly based on the [python-betterproto2](https://github.com/betterproto/python-betterproto2) library for handling protobufs. 

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