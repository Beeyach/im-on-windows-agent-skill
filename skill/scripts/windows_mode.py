#!/usr/bin/env python3
"""Probe Windows coding environments and flag shell/path mismatches."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable


WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
WSL_MOUNT = re.compile(r"^/mnt/([A-Za-z])(?:/|$)")
WSL_UNC = re.compile(
    r"^\\\\(?:wsl\$|wsl\.localhost)\\([^\\]+)(?:\\(.*))?$", re.IGNORECASE
)


def _test_override(name: str) -> str | None:
    return os.environ.get(f"WINDOWS_MODE_TEST_{name}")


def is_wsl() -> bool:
    override = _test_override("WSL")
    if override is not None:
        return override.lower() in {"1", "true", "yes"}
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(errors="ignore").lower()
    except OSError:
        return False


def platform_name() -> str:
    return (_test_override("PLATFORM") or platform.system()).lower()


def detect_shell() -> str:
    override = _test_override("SHELL")
    if override:
        return normalize_shell(override)
    if is_wsl():
        return "wsl"
    if os.environ.get("MSYSTEM") or "msys" in os.environ.get("OSTYPE", "").lower():
        return "bash"
    if platform_name() == "windows":
        shell_hint = " ".join(
            [
                os.environ.get("COMSPEC", ""),
                os.environ.get("PSModulePath", ""),
                os.environ.get("SHELL", ""),
            ]
        ).lower()
        if "powershell" in shell_hint or "pwsh" in shell_hint or os.environ.get("PSModulePath"):
            return "powershell"
        if "bash" in shell_hint or "sh.exe" in shell_hint:
            return "bash"
        return "cmd"
    shell = Path(os.environ.get("SHELL", "")).name.lower()
    return "bash" if shell in {"bash", "zsh", "fish", "sh"} else "unknown"


def normalize_shell(shell: str) -> str:
    value = shell.strip().lower()
    aliases = {
        "pwsh": "powershell",
        "powershell.exe": "powershell",
        "cmd.exe": "cmd",
        "git-bash": "bash",
        "msys": "bash",
        "msys2": "bash",
        "zsh": "bash",
        "sh": "bash",
    }
    return aliases.get(value, value)


def path_style(value: str) -> str:
    if WSL_UNC.match(value):
        return "wsl-unc"
    if value.startswith("\\\\"):
        return "windows-unc"
    if WINDOWS_DRIVE.match(value):
        return "windows-drive"
    if WSL_MOUNT.match(value):
        return "wsl-mounted-drive"
    if value.startswith("/"):
        return "posix"
    return "relative"


def convert_path(value: str, target: str, distro: str | None = None) -> str:
    style = path_style(value)
    if target == "wsl":
        if style == "windows-drive":
            drive = value[0].lower()
            tail = value[2:].replace("\\", "/").lstrip("/")
            return f"/mnt/{drive}/{tail}" if tail else f"/mnt/{drive}"
        match = WSL_UNC.match(value)
        if match:
            tail = (match.group(2) or "").replace("\\", "/")
            return f"/{tail}" if tail else "/"
        return value
    if target == "windows":
        match = WSL_MOUNT.match(value)
        if match:
            drive = match.group(1).upper()
            tail = value[6:].lstrip("/").replace("/", "\\")
            return f"{drive}:\\{tail}" if tail else f"{drive}:\\"
        if style == "posix" and distro:
            tail = value.lstrip("/").replace("/", "\\")
            return f"\\\\wsl.localhost\\{distro}\\{tail}"
        return value
    raise ValueError("target must be 'windows' or 'wsl'")


def classify_tool(path: str | None) -> str:
    if not path:
        return "missing"
    lowered = path.lower()
    if lowered.startswith("/mnt/") and lowered.endswith(".exe"):
        return "windows-from-wsl"
    if WINDOWS_DRIVE.match(path) or lowered.endswith(".exe") or lowered.startswith("\\\\"):
        return "windows"
    if path.startswith("/"):
        return "linux"
    return "unknown"


def probe(project_path: str, requested_shell: str = "auto") -> dict[str, object]:
    resolved = _test_override("PATH") or str(Path(project_path).expanduser().resolve())
    shell = detect_shell() if requested_shell == "auto" else normalize_shell(requested_shell)
    wsl = is_wsl()
    os_name = platform_name()
    tools = {}
    for name in ("git", "node", "npm", "python", "python3", "py", "rg", "pwsh", "powershell", "bash", "wsl"):
        found = shutil.which(name)
        tools[name] = {"path": found, "kind": classify_tool(found)}

    risks: list[str] = []
    style = path_style(resolved)
    if wsl and style == "wsl-mounted-drive":
        risks.append("Project is inside WSL but stored on a mounted Windows drive; file watching and I/O may differ.")
    if os_name == "windows" and style == "wsl-unc":
        risks.append("A Windows process is accessing a WSL filesystem through UNC; run project tools inside WSL when possible.")
    runtime_kinds = {
        data["kind"]
        for key, data in tools.items()
        if key in {"git", "node", "python", "python3"} and data["kind"] != "missing"
    }
    if "linux" in runtime_kinds and ("windows" in runtime_kinds or "windows-from-wsl" in runtime_kinds):
        risks.append("Core tools resolve from both Windows and Linux runtimes.")

    environment = "wsl" if wsl else ("native-windows" if os_name == "windows" else os_name)
    return {
        "environment": environment,
        "shell": shell,
        "project_path": resolved,
        "path_style": style,
        "distro": os.environ.get("WSL_DISTRO_NAME") if wsl else None,
        "tools": tools,
        "risks": risks,
    }


def _contains_any(command: str, patterns: Iterable[str]) -> str | None:
    for pattern in patterns:
        if re.search(pattern, command, flags=re.IGNORECASE):
            return pattern
    return None


def check_command(command: str, shell: str, cwd: str) -> dict[str, object]:
    shell = normalize_shell(shell if shell != "auto" else detect_shell())
    command = command.strip()
    issues: list[dict[str, str]] = []

    def add(level: str, code: str, message: str, suggestion: str) -> None:
        issues.append({"level": level, "code": code, "message": message, "suggestion": suggestion})

    has_windows_path = bool(re.search(r"(?:^|[\s'\"])[A-Za-z]:[\\/]", command))
    has_wsl_path = bool(re.search(r"(?:^|[\s'\"])/mnt/[A-Za-z](?:/|\b)", command))

    if shell in {"powershell", "cmd"} and has_wsl_path:
        add("blocked", "wsl-path-in-native-shell", "The command uses a WSL mount path in a native Windows shell.", "Use the equivalent Windows path or deliberately run the command inside WSL.")
    if shell == "wsl" and has_windows_path:
        add("blocked", "windows-path-in-wsl", "The command uses a Windows drive path directly inside WSL.", "Convert it with wslpath or use the Linux project path.")
    if shell == "bash" and has_wsl_path and platform_name() == "windows" and not is_wsl():
        add("blocked", "wsl-path-in-git-bash", "Git Bash is not WSL, so /mnt/<drive> is not a reliable native path.", "Use the Git Bash drive form such as /c/path or a quoted Windows path accepted by the tool.")

    if shell == "powershell":
        if _contains_any(command, [r"(^|[;&|]\s*)export\s+", r"(^|[;&|]\s*)source\s+", r"\b2>\s*/dev/null\b", r"<<\s*['\"]?[A-Za-z_]"]):
            add("blocked", "bash-syntax", "The command contains Bash-only syntax.", "Rewrite it with PowerShell environment variables, dot-sourcing, redirection, or a here-string.")
        if _contains_any(command, [r"(^|[;&|]\s*)rm\s+-[^\r\n]*[rf]", r"(^|[;&|]\s*)mkdir\s+-p\b", r"(^|[;&|]\s*)chmod\b", r"(^|[;&|]\s*)chown\b"]):
            add("blocked", "unix-command-shape", "The command relies on Unix flags or permissions that PowerShell does not implement the same way.", "Use a PowerShell-native command and literal paths.")
        if re.search(r"(^|[;&|]\s*)[A-Za-z_][A-Za-z0-9_]*=\S+\s+\S+", command):
            add("blocked", "posix-env-assignment", "Inline POSIX environment assignment is not valid PowerShell syntax.", "Set $env:NAME for the command, then restore or remove it afterward.")
        if "&&" in command:
            add("review", "powershell-version-chain", "The && operator requires modern PowerShell and may fail in Windows PowerShell 5.1.", "Use an explicit $LASTEXITCODE check when the supported PowerShell version is unknown.")
        if re.search(r"(?<!\$env:)\$[A-Za-z_][A-Za-z0-9_]*", command) and "$env:" not in command.lower():
            add("review", "environment-variable-syntax", "A $NAME token in PowerShell is a shell variable, not an environment variable.", "Use $env:NAME when the child process must receive it.")

    if shell == "cmd":
        if _contains_any(command, [r"\$env:", r"\bGet-(?:ChildItem|Content|Command|Process)\b", r"\bRemove-Item\b", r"\bNew-Item\b"]):
            add("blocked", "powershell-in-cmd", "The command contains PowerShell syntax but the selected shell is cmd.exe.", "Run it through PowerShell explicitly or rewrite it for cmd.exe.")
        if _contains_any(command, [r"(^|[&|]\s*)export\s+", r"\b2>\s*/dev/null\b", r"(^|[&|]\s*)source\s+"]):
            add("blocked", "bash-in-cmd", "The command contains Bash syntax but the selected shell is cmd.exe.", "Rewrite it for cmd.exe or deliberately use Git Bash/WSL.")

    if shell in {"bash", "wsl"}:
        if _contains_any(command, [r"\$env:", r"\bGet-(?:ChildItem|Content|Command|Process)\b", r"\bRemove-Item\b", r"\bNew-Item\b", r"\$LASTEXITCODE\b"]):
            add("blocked", "powershell-in-posix-shell", "The command contains PowerShell syntax in a POSIX shell.", "Rewrite it for Bash or run PowerShell explicitly for a Windows-only resource.")

    cwd_style = path_style(cwd)
    if shell == "wsl" and cwd_style in {"windows-drive", "wsl-unc"}:
        add("blocked", "wsl-cwd-mismatch", "The selected WSL shell and working directory use incompatible path forms.", "Open the project from its Linux path inside the selected WSL distribution.")
    if shell in {"powershell", "cmd"} and cwd_style == "posix":
        add("review", "native-shell-posix-cwd", "The native Windows shell was given a POSIX working directory.", "Confirm whether this session is actually WSL or Git Bash before running the command.")
    if shell in {"powershell", "cmd"} and cwd_style == "wsl-unc":
        add("review", "native-shell-wsl-filesystem", "The native Windows shell is operating through a WSL UNC path.", "Prefer running project tools inside WSL to avoid path, watcher, and permission drift.")

    levels = {issue["level"] for issue in issues}
    status = "blocked" if "blocked" in levels else ("review" if issues else "safe")
    return {"status": status, "shell": shell, "cwd": cwd, "command": command, "issues": issues}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)

    probe_parser = sub.add_parser("probe", help="Inspect the current execution environment")
    probe_parser.add_argument("--path", default=".", help="Project path to classify")
    probe_parser.add_argument("--shell", default="auto", choices=["auto", "powershell", "cmd", "bash", "wsl"])

    check_parser = sub.add_parser("check", help="Flag shell and path mismatches")
    check_parser.add_argument("--shell", default="auto", choices=["auto", "powershell", "cmd", "bash", "wsl"])
    check_parser.add_argument("--cwd", default=".")
    check_parser.add_argument("command", nargs=argparse.REMAINDER)

    path_parser = sub.add_parser("path", help="Convert common Windows and WSL path forms")
    path_parser.add_argument("--to", required=True, choices=["windows", "wsl"])
    path_parser.add_argument("--distro")
    path_parser.add_argument("value")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.action == "probe":
        result = probe(args.path, args.shell)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.action == "path":
        print(convert_path(args.value, args.to, args.distro))
        return 0

    command_parts = args.command
    if command_parts and command_parts[0] == "--":
        command_parts = command_parts[1:]
    if not command_parts:
        print("error: provide a command after --", file=sys.stderr)
        return 64
    result = check_command(" ".join(command_parts), args.shell, args.cwd)
    print(json.dumps(result, indent=2, sort_keys=True))
    return {"safe": 0, "review": 1, "blocked": 2}[str(result["status"])]


if __name__ == "__main__":
    raise SystemExit(main())
