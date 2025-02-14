# betterosi: library for osi

its [osi3](https://github.com/OpenSimulationInterface/open-simulation-interface) using [betterproto2](https://github.com/betterproto/python-betterproto2).

- supports writing and reading either mcap or osi files with `betterosi.Writer` and `betterosi.read`
- View OSI or MCAP file containing OSI GroundTruth `betterosi-viewer <filepath.mcap / filepath.osi>`
- Convert osi to mcap with `betterosi-to-mcap <filepath to osi>`

## Install

`pip install git+https://gitlab+deploy-token-147:gldt-nUtxxKzFkxtgbKngy5U-@gitlab.ika.rwth-aachen.de/fb-fi/projects/synergies/betterosi`

## Read OSI and MCAP
The following code creates a list of ground truths form mcap or osi sensor views or ground truth messages.
```python
import betterosi

ground_truths = betterosi.read('filepath.mcap/filepath.osi')
sensor_views = betterosi.read('filepath.osi', return_sensorview=True)

```
## Writing MCAP file
With the following code you can create an MCAP file. If you change the filepath `test.mcap` and `.osi` file will be created automatically.

### Create MCAP

```python
with betterosi.Writer(f'test.mcap') as writer:
    writer.add(some_ground_truth_or_sensor_view)
```

### Create OSI
```python
with betterosi.Writer(f'test.osi') as writer:
    writer.add(some_ground_truth_or_sensor_view)
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