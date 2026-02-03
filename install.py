#!/usr/bin/env python3
import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def find_player_script() -> Path | None:
    """Search for ascii_player.py in multiple locations."""
    search_locations = [
        # Same directory as install.py
        Path(__file__).resolve().parent / "ascii_player.py",
        # Current working directory
        Path.cwd() / "ascii_player.py",
        # Parent directories (up to 3 levels)
        Path.cwd().parent / "ascii_player.py",
        Path.cwd().parent.parent / "ascii_player.py",
        Path.cwd().parent.parent.parent / "ascii_player.py",
        # Common install locations
        Path.home() / ".local" / "share" / "cubeplayer" / "ascii_player.py",
        Path.home() / "cubeplayer" / "ascii_player.py",
    ]
    
    # Windows-specific locations
    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if local_app:
            base = Path(local_app)
            search_locations.extend([
                base / "cubeplayer" / "ascii_player.py",
                base / "Programs" / "cubeplayer" / "ascii_player.py",
            ])
    
    # Search in all locations
    for location in search_locations:
        try:
            if location.exists() and location.is_file():
                print(f"Found ascii_player.py at: {location}")
                return location.resolve()
        except (OSError, RuntimeError):
            continue
    
    return None


PROJECT_ROOT = Path(__file__).resolve().parent
PLAYER_SCRIPT = find_player_script() or PROJECT_ROOT / "ascii_player.py"


def is_writable_dir(path: Path) -> bool:
    """Check if a path exists, is a directory, and is writable."""
    try:
        return path.is_dir() and os.access(path, os.W_OK)
    except (OSError, PermissionError):
        return False


def first_writable_in_path() -> Path | None:
    """Find the first writable directory in the system PATH."""
    path_env = os.environ.get("PATH", "")
    if not path_env:
        return None
    for entry in path_env.split(os.pathsep):
        if not entry:
            continue
        try:
            candidate = Path(entry).expanduser().resolve()
            if is_writable_dir(candidate):
                return candidate
        except (OSError, RuntimeError):
            continue
    return None


def default_user_bin() -> Path:
    """Return the default user bin directory for the current platform."""
    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = Path(local_app) if local_app else Path.home() / "AppData" / "Local"
        return base / "cubeplayer" / "bin"
    return Path.home() / ".local" / "bin"


def ensure_dir(path: Path) -> bool:
    """Create directory with all parent directories, return success status."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except (OSError, PermissionError) as exc:
        print(f"Error creating directory {path}: {exc}")
        return False


def add_to_unix_path(target_dir: Path) -> bool:
    """Add directory to PATH in Unix shell profile files."""
    shell_files = [
        Path.home() / ".bashrc",
        Path.home() / ".zshrc",
        Path.home() / ".profile",
        Path.home() / ".bash_profile",
    ]
    
    export_line = f'export PATH="$PATH:{target_dir}"\n'
    marker_start = "# cubeplayer PATH - added by install.py\n"
    marker_end = "# end cubeplayer PATH\n"
    full_block = f"{marker_start}{export_line}{marker_end}"
    
    added_to_any = False
    for shell_file in shell_files:
        if not shell_file.exists():
            continue
        
        try:
            content = shell_file.read_text(encoding="utf-8", errors="replace")
            
            # Check if already added
            if marker_start in content:
                print(f"  PATH already configured in {shell_file.name}")
                added_to_any = True  # Count as success if already configured
                continue
            
            # Add to end of file
            with shell_file.open("a", encoding="utf-8") as f:
                f.write("\n" + full_block)
            print(f"  ✓ Added PATH to {shell_file.name}")
            added_to_any = True
            
        except (OSError, PermissionError) as exc:
            print(f"  Warning: Could not modify {shell_file.name}: {exc}")
    
    return added_to_any


def add_to_windows_path(target_dir: Path) -> bool:
    """Add directory to Windows user PATH via registry."""
    try:
        import winreg
        
        # Open user environment variables key
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE
        )
        
        # Get current PATH
        try:
            current_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""
        
        # Check if already in PATH
        path_entries = [p.strip() for p in current_path.split(";") if p.strip()]
        target_str = str(target_dir)
        
        # Safe comparison with error handling
        def paths_equal(p1: str, p2: Path) -> bool:
            try:
                return Path(p1).resolve() == p2.resolve()
            except (OSError, RuntimeError):
                return False
        
        if any(paths_equal(p, target_dir) for p in path_entries):
            print(f"  PATH already configured in Windows Environment Variables")
            winreg.CloseKey(key)
            return True
        
        # Add to PATH
        new_path = f"{current_path};{target_str}" if current_path else target_str
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)
        
        # Broadcast environment change (optional, may fail on some systems)
        try:
            import ctypes
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")
        except Exception:
            pass  # Not critical if broadcast fails
        
        print(f"  ✓ Added PATH to Windows Environment Variables")
        return True
        
    except ImportError:
        print("  Warning: winreg module not available")
        return False
    except Exception as exc:
        print(f"  Warning: Could not modify Windows PATH: {exc}")
        return False


def write_unix_launcher(target_dir: Path) -> Path | None:
    """Create Unix launcher script for cubeplayer."""
    target = target_dir / "cubeplayer"
    try:
        if target.exists():
            if target.is_dir():
                print(f"Removing existing directory: {target}")
                shutil.rmtree(target)
            else:
                print(f"Overwriting existing file: {target}")
        
        python_exe = sys.executable
        if not python_exe:
            print("Error: Could not determine Python executable path.")
            return None
        
        content = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -e",
                f'exec "{python_exe}" "{PLAYER_SCRIPT}" "$@"',
                "",
            ]
        )
        target.write_text(content, encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return target
    except (OSError, PermissionError) as exc:
        print(f"Error creating launcher {target}: {exc}")
        return None


def write_windows_launchers(target_dir: Path) -> list[Path]:
    """Create Windows launcher scripts (.cmd and .ps1) for cubeplayer."""
    python_exe = sys.executable
    if not python_exe:
        print("Error: Could not determine Python executable path.")
        return []
    
    created = []
    
    # Create .cmd launcher
    cmd_target = target_dir / "cubeplayer.cmd"
    try:
        if cmd_target.exists():
            if cmd_target.is_dir():
                print(f"Removing existing directory: {cmd_target}")
                shutil.rmtree(cmd_target)
            else:
                print(f"Overwriting existing file: {cmd_target}")
        
        cmd_target.write_text(
            "\n".join(
                [
                    "@echo off",
                    f'"{python_exe}" "{PLAYER_SCRIPT}" %*',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        created.append(cmd_target)
    except (OSError, PermissionError) as exc:
        print(f"Error creating launcher {cmd_target}: {exc}")
    
    # Create .ps1 launcher
    ps_target = target_dir / "cubeplayer.ps1"
    try:
        if ps_target.exists():
            if ps_target.is_dir():
                print(f"Removing existing directory: {ps_target}")
                shutil.rmtree(ps_target)
            else:
                print(f"Overwriting existing file: {ps_target}")
        
        ps_target.write_text(
            "\n".join(
                [
                    f'& "{python_exe}" "{PLAYER_SCRIPT}" $args',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        created.append(ps_target)
    except (OSError, PermissionError) as exc:
        print(f"Error creating launcher {ps_target}: {exc}")
    
    return created


def run_command(command: list[str], ignore_errors: bool = False) -> bool:
    """Run a shell command and return success status."""
    if not command:
        print("Error: Empty command provided.")
        return False
    
    print("Running:", " ".join(command))
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.stdout:
            print(result.stdout)
        return True
    except FileNotFoundError:
        print(f"Command not found: {command[0]}")
        return False
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}.")
        if exc.stderr:
            print(f"Error output: {exc.stderr}")
        return ignore_errors
    except Exception as exc:
        print(f"Unexpected error running command: {exc}")
        return False


def detect_linux_distro() -> tuple[str | None, str | None]:
    """Detect Linux distribution from /etc/os-release."""
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        return None, None
    
    try:
        data = os_release.read_text(encoding="utf-8", errors="ignore")
    except (OSError, PermissionError):
        return None, None
    
    distro_id = None
    id_like = None
    for line in data.splitlines():
        line = line.strip()
        if line.startswith("ID="):
            distro_id = line.split("=", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("ID_LIKE="):
            id_like = line.split("=", 1)[1].strip().strip('"').strip("'")
    return distro_id, id_like


def install_system_packages() -> bool:
    """Install system packages. Returns True if successful or if user should continue anyway."""
    print("\n=== Installing system dependencies ===\n")
    
    if os.name == "nt":
        # Windows
        if shutil.which("winget"):
            print("Attempting to install Python via winget...")
            run_command(["winget", "install", "--id", "Python.Python.3", "-e"], ignore_errors=True)
        else:
            print("winget not found. Please install Python manually from https://python.org/")
        
        print("\nInstalling pygame and mutagen via pip (system packages unavailable on Windows).")
        # Try without --user first (may fail in some Python installations on Windows)
        if not run_command([sys.executable, "-m", "pip", "install", "pygame", "mutagen"], ignore_errors=True):
            # Fallback to --user if normal install fails
            if not run_command([sys.executable, "-m", "pip", "install", "--user", "pygame", "mutagen"], ignore_errors=True):
                print("Warning: Failed to install Python packages via pip.")
                print("You may need to install pygame and mutagen manually.")
        return True

    if sys.platform == "darwin":
        # macOS
        if not shutil.which("brew"):
            print("Homebrew is required on macOS. Install it from https://brew.sh/")
            print("After installing Homebrew, run this installer again.")
            print("\nContinuing with launcher installation (you'll need to install dependencies manually)...")
            return True  # Allow continuation without Homebrew
        
        print("Installing Python via Homebrew...")
        run_command(["brew", "install", "python"], ignore_errors=True)
        
        print("Attempting to install pygame and mutagen via Homebrew...")
        # Note: pygame/mutagen might not be in Homebrew, so always try pip fallback
        run_command(["brew", "install", "pygame"], ignore_errors=True)
        run_command(["brew", "install", "mutagen"], ignore_errors=True)
        
        # Always try pip as well to ensure packages are available
        print("Installing/upgrading pygame and mutagen via pip...")
        if not run_command([sys.executable, "-m", "pip", "install", "--user", "--upgrade", "pygame", "mutagen"], ignore_errors=True):
            print("Warning: Failed to install Python packages via pip.")
            print("You may need to install pygame and mutagen manually.")
        return True

    # Linux
    distro_id, id_like = detect_linux_distro()
    
    # Check distro ID first
    if distro_id in {"ubuntu", "debian", "linuxmint", "pop"}:
        print(f"Detected Debian/Ubuntu-based distro: {distro_id}")
        if not run_command(["sudo", "apt", "update"], ignore_errors=True):
            print("Warning: apt update failed. Continuing anyway...")
        if run_command(
            [
                "sudo",
                "apt",
                "install",
                "-y",
                "python3",
                "python3-pip",
                "python3-pygame",
                "python3-mutagen",
            ]
        ):
            return True
        print("Warning: apt install failed. You may need to install packages manually.")
        return True
    
    if distro_id in {"fedora"}:
        print(f"Detected Fedora: {distro_id}")
        if run_command(
            [
                "sudo",
                "dnf",
                "install",
                "-y",
                "python3",
                "python3-pip",
                "python3-pygame",
                "python3-mutagen",
            ]
        ):
            return True
        print("Warning: dnf install failed. You may need to install packages manually.")
        return True
    
    if distro_id in {"arch", "manjaro", "cachyos", "endeavouros", "garuda"}:
        print(f"Detected Arch-based distro: {distro_id}")
        if run_command(
            [
                "sudo",
                "pacman",
                "-S",
                "--needed",
                "--noconfirm",
                "python",
                "python-pip",
                "python-pygame",
                "python-mutagen",
            ]
        ):
            return True
        print("Warning: pacman install failed. You may need to install packages manually.")
        return True
    
    # Fallback: check ID_LIKE for derivatives
    if id_like:
        if "debian" in id_like or "ubuntu" in id_like:
            print(f"Detected Debian/Ubuntu-based distro via ID_LIKE: {id_like}")
            if not run_command(["sudo", "apt", "update"], ignore_errors=True):
                print("Warning: apt update failed. Continuing anyway...")
            if run_command(
                [
                    "sudo",
                    "apt",
                    "install",
                    "-y",
                    "python3",
                    "python3-pip",
                    "python3-pygame",
                    "python3-mutagen",
                ]
            ):
                return True
            print("Warning: apt install failed. You may need to install packages manually.")
            return True
        
        if "arch" in id_like:
            print(f"Detected Arch-based distro via ID_LIKE: {id_like}")
            if run_command(
                [
                    "sudo",
                    "pacman",
                    "-S",
                    "--needed",
                    "--noconfirm",
                    "python",
                    "python-pip",
                    "python-pygame",
                    "python-mutagen",
                ]
            ):
                return True
            print("Warning: pacman install failed. You may need to install packages manually.")
            return True
        
        if "fedora" in id_like or "rhel" in id_like:
            print(f"Detected Fedora/RHEL-based distro via ID_LIKE: {id_like}")
            if run_command(
                [
                    "sudo",
                    "dnf",
                    "install",
                    "-y",
                    "python3",
                    "python3-pip",
                    "python3-pygame",
                    "python3-mutagen",
                ]
            ):
                return True
            print("Warning: dnf install failed. You may need to install packages manually.")
            return True

    print(f"Unsupported Linux distro (ID={distro_id}, ID_LIKE={id_like}).")
    print("Please install Python, pygame, and mutagen manually using your package manager.")
    print("Continuing with launcher installation...")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Install cubeplayer launchers and dependencies.")
    parser.add_argument(
        "--skip-system",
        action="store_true",
        help="Skip system package installation and only create launchers.",
    )
    args = parser.parse_args()

    # Verify player script exists
    if not PLAYER_SCRIPT.exists():
        print(f"Error: Player script 'ascii_player.py' not found.")
        print("\nSearched in:")
        print(f"  - {Path(__file__).resolve().parent}")
        print(f"  - {Path.cwd()}")
        print(f"  - Parent directories (up to 3 levels)")
        print(f"  - {Path.home() / '.local' / 'share' / 'cubeplayer'}")
        print(f"  - {Path.home() / 'cubeplayer'}")
        if os.name == "nt":
            local_app = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            if local_app:
                print(f"  - {Path(local_app) / 'cubeplayer'}")
        print("\nPlease cd to the cubeplayer directory or specify the path.")
        return 1

    # Install system packages
    if not args.skip_system:
        if not install_system_packages():
            print("\nSystem package installation failed.")
            response = input("Continue with launcher installation anyway? (y/n): ").strip().lower()
            if response not in {"y", "yes"}:
                print("Installation cancelled.")
                return 1

    # Determine target directory
    print("\n=== Installing launcher scripts ===\n")
    target_dir = first_writable_in_path() or default_user_bin()
    
    if not ensure_dir(target_dir):
        print(f"\nError: Could not create directory {target_dir}")
        print("Installation failed. Check permissions and try again.")
        return 1

    # Create launcher scripts
    if os.name == "nt":
        targets = write_windows_launchers(target_dir)
    else:
        launcher = write_unix_launcher(target_dir)
        targets = [launcher] if launcher else []

    if not targets:
        print("\nError: Failed to create any launcher scripts.")
        return 1

    print("\n✓ Installed cubeplayer launcher(s):")
    for target in targets:
        print(f"  {target}")

    # Check and configure PATH
    def safe_resolve_path(p: str) -> str | None:
        try:
            return str(Path(p).resolve())
        except (OSError, RuntimeError):
            return None
    
    path_entries = [resolved for p in os.environ.get("PATH", "").split(os.pathsep) 
                    if p and (resolved := safe_resolve_path(p)) is not None]
    
    try:
        target_dir_resolved = str(target_dir.resolve())
    except (OSError, RuntimeError) as exc:
        print(f"Warning: Could not resolve target directory path: {exc}")
        target_dir_resolved = str(target_dir)
    
    if target_dir_resolved not in path_entries:
        print(f"\n=== Configuring PATH ===\n")
        print(f"Adding {target_dir} to your PATH...\n")
        
        if os.name == "nt":
            # Windows: modify registry
            if add_to_windows_path(target_dir):
                print("\n✓ PATH configured! Open a NEW terminal/PowerShell window and run 'cubeplayer'")
                print("  (Current terminal won't see the change)")
            else:
                print("\n⚠ Could not automatically configure PATH.")
                print("Please add manually via Environment Variables:")
                print("  1. Search for 'Environment Variables' in Start menu")
                print("  2. Edit 'Path' under User variables")
                print(f"  3. Add: {target_dir}")
        else:
            # Unix: modify shell profiles
            if add_to_unix_path(target_dir):
                print("\n✓ PATH configured! Restart your terminal or run:")
                print(f"  source ~/.bashrc  # or ~/.zshrc depending on your shell")
                print("\nThen you can run 'cubeplayer' from anywhere!")
            else:
                print("\n⚠ Could not automatically configure PATH.")
                print("Please add manually to your shell profile (e.g. ~/.bashrc or ~/.zshrc):")
                print(f'  export PATH="$PATH:{target_dir}"')
    else:
        print(f"\n✓ Installation complete! Run 'cubeplayer' from any directory.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
