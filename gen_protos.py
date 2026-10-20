import argparse
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).parent
proto_root = root / "osi-proto"
gen_root = root / "betterosi" / "generated"
gen_root.mkdir(parents=True, exist_ok=True)

available_dirs = {
    d.name: d for d in proto_root.iterdir() if d.is_dir() and any(d.glob("*.proto"))
}

if not available_dirs:
    print(f"No proto version directories found in {proto_root}", file=sys.stderr)
    sys.exit(1)


def resolve_version_dir(req: str) -> Path | None:
    """Resolve a version specifier (e.g. '3.8', '3.8.0', 'v3_8') to a directory."""
    clean = req.lstrip("v").replace("_", ".")
    # 1. Exact match
    if clean in available_dirs:
        return available_dirs[clean]
    # 2. Prefix match with dot (e.g. '3.8' -> '3.8.0')
    matches = [
        name
        for name in sorted(available_dirs.keys())
        if name.startswith(clean + ".") or name == clean
    ]
    if matches:
        return available_dirs[matches[0]]
    # 3. General prefix match
    matches = [name for name in sorted(available_dirs.keys()) if name.startswith(clean)]
    if matches:
        return available_dirs[matches[0]]
    return None


parser = argparse.ArgumentParser(
    description="Generate Python protobuf code for ASAM OSI versions."
)
parser.add_argument(
    "versions",
    nargs="*",
    help="OSI versions to generate (e.g. 3.8, 3.7, 3.8.0). If omitted, generates all available versions.",
)
args = parser.parse_args()

if args.versions:
    version_dirs = []
    seen = set()
    for req in args.versions:
        v_dir = resolve_version_dir(req)
        if v_dir is None:
            print(
                f"Error: Version '{req}' not found in {proto_root}. "
                f"Available: {', '.join(sorted(available_dirs.keys()))}",
                file=sys.stderr,
            )
            sys.exit(1)
        if v_dir not in seen:
            seen.add(v_dir)
            version_dirs.append(v_dir)
else:
    version_dirs = sorted(
        available_dirs.values(),
        key=lambda d: [int(x) if x.isdigit() else x for x in d.name.split(".")],
    )

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
                    if name not in all_names:
                        all_names.append(name)
        init_content = "\n".join(imports) + "\n\n__all__ = [\n"
        init_content += "".join(f'    "{n}",\n' for n in all_names)
        init_content += "]\n"
        (outdir / "__init__.py").write_text(init_content)

# Ensure betterosi/generated/__init__.py exists
gen_init = gen_root / "__init__.py"
if not gen_init.exists():
    gen_init.write_text(
        "from betterosi.version_manager import (\n"
        "    DEFAULT_VERSION,\n"
        "    get_available_versions,\n"
        "    load_generated_version,\n"
        ")\n\n"
        "_default_mod = load_generated_version(DEFAULT_VERSION)\n"
        '__all__ = list(getattr(_default_mod, "__all__", []))\n\n'
        "for _name in __all__:\n"
        "    globals()[_name] = getattr(_default_mod, _name)\n"
    )

print("Protobuf code generation completed successfully.")
