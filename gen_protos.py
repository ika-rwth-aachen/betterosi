import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).parent
proto_root = root / "osi-proto"
gen_root = root / "betterosi" / "generated"
gen_root.mkdir(parents=True, exist_ok=True)

version_dirs = sorted(
    [d for d in proto_root.iterdir() if d.is_dir() and any(d.glob("*.proto"))],
    key=lambda d: [int(x) if x.isdigit() else x for x in d.name.split(".")],
)

if not version_dirs:
    print(f"No proto version directories found in {proto_root}", file=sys.stderr)
    sys.exit(1)

for v_dir in version_dirs:
    version = v_dir.name
    outdir = gen_root / version
    outdir.mkdir(parents=True, exist_ok=True)

    template = {
        "version": "v2",
        "plugins": [
            {
                "local": "protoc-gen-py",
                "out": str(outdir),
            }
        ],
    }

    print(f"Generating Python code for OSI {version}...")
    result = subprocess.run(
        ["buf", "generate", "--template", json.dumps(template)],
        cwd=v_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    print(f"Building descriptor set for OSI {version}...")
    result = subprocess.run(
        ["buf", "build", "-o", str(outdir / "osi3_descriptor_set.pb")],
        cwd=v_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    pb_files = sorted(outdir.glob("*_pb.py"))
    if pb_files:
        imports = [f"from .{f.stem} import *" for f in pb_files]
        all_names = []
        for f in pb_files:
            for line in f.read_text().splitlines():
                if line.startswith("class ") and "(" in line:
                    name = line.split("(")[0].replace("class ", "").strip()
                    all_names.append(name)
        init_content = "\n".join(imports) + "\n\n__all__ = [\n"
        init_content += "".join(f'    "{n}",\n' for n in all_names)
        init_content += "]\n"
        (outdir / "__init__.py").write_text(init_content)

print("Protobuf code generation completed successfully.")
