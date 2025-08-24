from pathlib import Path
import sys

try:
    import cairosvg
except Exception as e:
    print("CairoSVG not available:", e, file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images"

PAIRS = [
    (IMG / "architecture.svg", IMG / "architecture.png"),
    (IMG / "command_flow.svg", IMG / "command_flow.png"),
    (IMG / "ci_pipeline.svg", IMG / "ci_pipeline.png"),
]

for src, dst in PAIRS:
    if not src.exists():
        print(f"Missing {src}")
        continue
    print(f"Converting {src.name} -> {dst.name}")
    cairosvg.svg2png(url=str(src), write_to=str(dst), output_width=980)
print("Done.")
