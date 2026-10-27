from pathlib import Path
import re

p = Path("modules/ownership/importer.py")
content = p.read_text(encoding="utf-8")

# 1. Update get_user_mappings_dir and add validate_mapping_schema
old_get_user = '''def get_user_mappings_dir() -> Path:
    """Return user-specific mappings directory (~/.clearance_check/import_mappings/)."""
    user_dir = Path.home() / ".clearance_check" / "import_mappings"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir'''

new_get_user = '''ALLOWED_TRANSFORMS_AND_TYPES = {
    "string", "str", "float", "int", "integer", "boolean", "bool",
    "percentage", "strip", "lowercase", "uppercase", "iso_country",
}


def validate_mapping_schema(data: Any) -> Tuple[bool, str]:
    """
    Validate mapping file schema (Req 13):
    - Must be a dictionary
    - Must contain 'name', 'version', and 'columns'
    - 'columns' must be a dictionary
    - Refuses any unknown transforms, executable tags, or arbitrary code handlers
    """
    if not isinstance(data, dict):
        return False, "Mapping configuration must be a YAML dictionary"

    for req_field in ["name", "version", "columns"]:
        if req_field not in data:
            return False, f"Missing required mapping field: '{req_field}'"

    cols = data.get("columns")
    if not isinstance(cols, dict):
        return False, "Field 'columns' must be a dictionary of column definitions"

    for col_name, col_def in cols.items():
        if not isinstance(col_def, dict):
            return False, f"Column definition for '{col_name}' must be a dictionary"
        c_type = col_def.get("type")
        if c_type and str(c_type).lower() not in ALLOWED_TRANSFORMS_AND_TYPES:
            return False, f"Refused unknown transform/type '{c_type}' for column '{col_name}'"
        c_transform = col_def.get("transform")
        if c_transform and str(c_transform).lower() not in ALLOWED_TRANSFORMS_AND_TYPES:
            return False, f"Refused unknown transform/type '{c_transform}' for column '{col_name}'"

    return True, "Valid"


def get_user_mappings_dir() -> Path:
    """Return user-specific mappings directory (%LOCALAPPDATA%/.../import_mappings/)."""
    from modules.common.paths import get_app_data_dir
    user_dir = get_app_data_dir() / "import_mappings"
    user_dir.mkdir(parents=True, exist_ok=True)
    # Migrate legacy ~/.clearance_check/import_mappings/ if present
    legacy_dir = Path.home() / ".clearance_check" / "import_mappings"
    if legacy_dir.is_dir():
        for f in legacy_dir.glob("*.yaml"):
            dest = user_dir / f.name
            if not dest.exists():
                try:
                    shutil.copy2(f, dest)
                except Exception:
                    pass
    return user_dir'''

assert old_get_user in content, "old_get_user not found"
content = content.replace(old_get_user, new_get_user)

# 2. Update load_mapping to validate schema and safe_load
old_load = '''def load_mapping(mapping_name: str = "clearance_template_v1.yaml") -> Dict[str, Any]:
    """Load column mapping configuration safely using yaml.safe_load only."""
    # Check user dir first, then built-in
    user_path = get_user_mappings_dir() / mapping_name
    if user_path.exists():
        with open(user_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    builtin_path = BUILTIN_MAPPINGS_DIR / mapping_name
    if builtin_path.exists():
        with open(builtin_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # Fallback to default
    default_path = BUILTIN_MAPPINGS_DIR / "clearance_template_v1.yaml"
    if default_path.exists():
        with open(default_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    return {}'''

new_load = '''def load_mapping(mapping_name: str = "clearance_template_v1.yaml") -> Dict[str, Any]:
    """Load column mapping configuration safely using yaml.safe_load only with schema validation."""
    target_path = None
    user_path = get_user_mappings_dir() / mapping_name
    if user_path.exists():
        target_path = user_path
    else:
        builtin_path = BUILTIN_MAPPINGS_DIR / mapping_name
        if builtin_path.exists():
            target_path = builtin_path
        else:
            default_path = BUILTIN_MAPPINGS_DIR / "clearance_template_v1.yaml"
            if default_path.exists():
                target_path = default_path

    if not target_path or not target_path.exists():
        return {}

    with open(target_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    is_valid, err_msg = validate_mapping_schema(data)
    if not is_valid:
        raise ValueError(f"Mapping '{mapping_name}' failed schema validation: {err_msg}")

    return data'''

assert old_load in content, "old_load not found"
content = content.replace(old_load, new_load)

p.write_text(content, encoding="utf-8")
print("modules/ownership/importer.py updated successfully!")
