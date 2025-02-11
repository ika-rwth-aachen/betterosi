from pathlib import Path

import typer

import betterosi

app = typer.Typer(pretty_exceptions_show_locals=False)

@app.command()
def osi2mcap(
    input: Path,
    output: Path|None = None
):
    input = Path(input)
    if output is None:
        output = f'{input.stem}.mcap'
    else:
        output = f'{Path(output).stem}.mcap'
    views = betterosi.read_ground_truth(input)
    with betterosi.Writer(output) as w:
        [w.add(v) for v in views]
        
if __name__ == '__main__':
    app.run()