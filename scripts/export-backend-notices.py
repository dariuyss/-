"""Export actual installed wheel notices, without importing third-party code."""
from importlib.metadata import distributions
from pathlib import Path

root = Path(__file__).resolve().parent.parent
output = root / "notices" / "backend-licenses.txt"
output.parent.mkdir(exist_ok=True)
sections = []
for dist in sorted(distributions(), key=lambda d: d.metadata.get("Name", "").lower()):
    name = dist.metadata.get("Name", "unknown")
    if name in {"pip", "setuptools"}:
        continue
    classifier = [c for c in dist.metadata.get_all("Classifier", []) if "License" in c]
    sections.append(f"\n{'=' * 72}\n{name}=={dist.version}\n" + "\n".join(classifier))
    if dist.metadata.get("License-Expression"):
        sections.append("License-Expression: " + dist.metadata["License-Expression"])
    if dist.metadata.get("License"):
        sections.append(dist.metadata["License"])
    for file in dist.files or []:
        if (".dist-info/" in str(file) and any(part.lower().startswith(("license", "licence", "copying", "notice")) for part in file.parts)):
            path = Path(dist.locate_file(file))
            if path.is_file():
                sections.append(f"\n--- {file} ---\n" + path.read_text(encoding="utf-8", errors="replace"))
output.write_text("\n".join(sections), encoding="utf-8")
print("Exported backend wheel notices.")
