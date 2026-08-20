from pathlib import Path

import typer

import betterosi

app = typer.Typer(pretty_exceptions_show_locals=False)


@app.command()
def osi2mcap(
    input: Path,
    output: Path | None = None,
    osi_message_type: str = "GroundTruth",
    topic: str = "ConvertedTrace",
    mode: str = "wb",
    description: str | None = None,
    zero_time: str | None = None,
):
    input = Path(input)
    if output is None:
        output = Path(f"{input.stem}.mcap")
    else:
        output = Path(output).with_suffix(".mcap")
    kwargs = {}
    if osi_message_type == "GroundTruth":
        kwargs["return_ground_truth"] = True
    elif osi_message_type == "SensorView":
        kwargs["return_sensor_view"] = True
    else:
        kwargs["osi_message_type"] = osi_message_type
    iterer = betterosi.read(input, **kwargs)
    try:
        from tqdm.auto import tqdm

        iterer = tqdm(iterer)
    except ImportError:
        pass

    metadata: dict[str, str] = {
        "description": description or f"Converted from {input.name}",
    }
    zt = zero_time or betterosi.extract_timestamp_from_filename(input)
    if zt:
        metadata["zero_time"] = zt

    with betterosi.Writer(output, mode=mode, topic=topic, metadata=metadata) as w:
        for message in iterer:
            w.add(message)


if __name__ == "__main__":
    app.run()
