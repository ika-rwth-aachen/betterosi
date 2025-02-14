from pathlib import Path

import typer
from tqdm.auto import tqdm
import betterosi

app = typer.Typer(pretty_exceptions_show_locals=False)

@app.command()
def osi2mcap(
    input: Path,
    output: Path|None = None,
    osi_message_type: str = 'GroundTruth',
    topic: str = "ConvertedTrace",
    mode: str = 'wb'
):
    input = Path(input)
    if output is None:
        output = f'{input.stem}.mcap'
    else:
        output = f'{Path(output).stem}.mcap'
    kwargs = {}
    if osi_message_type == 'GroundTruth':
        kwargs['return_ground_truth'] = True
    elif osi_message_type == 'SensorView':
        kwargs['return_sensor_view'] = True
    else:
        kwargs['osi_message_type'] = osi_message_type
    with betterosi.Writer(output, mode=mode, topic=topic) as w:
        for message in tqdm(betterosi.read(input, **kwargs)):
            w.add(message)
        
if __name__ == '__main__':
    app.run()