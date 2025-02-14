from pathlib import Path

import typer

import betterosi

app = typer.Typer(pretty_exceptions_show_locals=False)

@app.command()
def osi2mcap(
    input: Path,
    output: Path|None = None,
    use_sensorview: bool = False,
    topic: str = "ConvertedTrace",
    mode: str = 'wb'
):
    input = Path(input)
    if output is None:
        output = f'{input.stem}.mcap'
    else:
        output = f'{Path(output).stem}.mcap'
    views = betterosi.read(input, return_sensor_view=use_sensorview)
    with betterosi.Writer(output, mode=mode, topic=topic) as w:
        [w.add(v) for v in views]
        
if __name__ == '__main__':
    app.run()