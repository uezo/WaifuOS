import os
from pathlib import Path
import shutil


def resolve_console_script_path(waifu_command_path: str) -> Path:
    script_name = Path(waifu_command_path).name
    script_path = shutil.which(script_name)
    if script_path:
        return Path(script_path).resolve()
    return Path(waifu_command_path).resolve()


def alias_target_path(template: Path, alias_name: str, target_dir: Path) -> Path:
    suffix = "".join(template.suffixes)
    return target_dir / f"{alias_name}{suffix}"


def create_alias(waifu_command_path: str, alias_name: str, target_dir: str | None, prefer_copy: bool) -> Path:
    template = resolve_console_script_path(waifu_command_path)
    destination_dir = Path(target_dir).expanduser() if target_dir else template.parent
    destination_dir.mkdir(parents=True, exist_ok=True)

    # Create alias
    alias_path = alias_target_path(template, alias_name, destination_dir.resolve())
    if alias_path.exists():
        raise FileExistsError(f"{alias_path} already exists")
    if os.name != "nt" and not prefer_copy:
        try:
            alias_path.symlink_to(template)
            return alias_path
        except OSError as exc:
            print(f"Symlink creation failed, falling back to file copy: {exc}")

    # Copy instead of alias
    shutil.copy2(template, alias_path)
    alias_path.chmod(template.stat().st_mode)

    # Copy pip's companion helper if present (e.g. <name>-script.py on Windows installations)
    helper_name = f"{template.stem}-script.py"
    helper_path = template.with_name(helper_name)
    if helper_path.exists():
        helper_alias = alias_path.with_name(f"{alias_path.stem}-script.py")
        if not helper_alias.exists():
            shutil.copy2(helper_path, helper_alias)
            helper_alias.chmod(helper_path.stat().st_mode)

    return alias_path
