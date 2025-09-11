# uv pip install betterproto2_compiler grpcio-tools
import sys
from pathlib import Path
from grpc_tools import protoc
import os
import importlib.resources
import shutil

with importlib.resources.path("grpc_tools", "_proto") as proto_include:
    protos = Path(__file__).parent / "osi-proto"
    protos_include_cp = protos / "google/protobuf"
    protos_include_cp.mkdir(exist_ok=True, parents=True)
    for p in proto_include.glob("**/*.proto"):
        shutil.copy(p, protos_include_cp / p.name)
    files = [str(f.relative_to(protos)) for f in protos.glob("**/*.proto")]
    outdir = Path(__file__).parent / ("./betterosi/generated/")
    outdir.mkdir(exist_ok=True)
    cwd = os.getcwd()  # Save current directory
    try:
        os.chdir(protos)  # Change to output directory
        result = protoc.main(
            [
                "",
                f"--python_betterproto2_out={outdir}",
                "--python_betterproto2_opt=google_protobuf_descriptors",
                *files,
            ]
        )  # Use '.' as output
    finally:
        os.chdir(cwd)  # Restore original directory
sys.exit(result)
