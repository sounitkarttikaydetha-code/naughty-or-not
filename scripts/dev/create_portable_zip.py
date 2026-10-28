import zipfile
from pathlib import Path
import hashlib

src_dir = Path("dist/NaughtyOrNot")
zip_path = Path("dist/installer/ClearanceCheck_v1.1.3_Portable.zip")
zip_path.parent.mkdir(parents=True, exist_ok=True)

print(f"Creating {zip_path} from {src_dir}...")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for item in src_dir.rglob("*"):
        if item.is_file():
            arcname = item.relative_to(src_dir)
            zf.write(item, arcname)

hasher = hashlib.sha256()
with open(zip_path, "rb") as f:
    for chunk in iter(lambda: f.read(65536), b""):
        hasher.update(chunk)
sha = hasher.hexdigest()
print(f"Portable Zip created successfully: {zip_path} (Size: {zip_path.stat().st_size} bytes)")
print(f"SHA-256: {sha}")
