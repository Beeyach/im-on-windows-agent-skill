---
name: im-on-windows
description: Keep Claude Code or Codex reliable on native Windows, PowerShell, cmd.exe, Git Bash, MSYS2, or WSL without mixing shells, path styles, runtimes, or process commands. Use whenever the user says they are on Windows or WSL, uses Windows paths or PowerShell, reports Unix commands failing on Windows, has WSL/native toolchain confusion, line-ending churn, locked files or ports, or needs Windows-safe setup, build, test, and cleanup commands.
---

# I'm on Windows

Keep one execution environment consistent. Detect the shell, runtime, project location, and toolchain before choosing commands. Do not treat Windows as PowerShell by default, and do not treat WSL as a path translator for native Windows work.

## Start the mode

1. Say `Windows-aware mode active.`
2. Resolve this skill's directory from the loaded `SKILL.md`.
3. Probe without changing the machine:

```text
python <skill-dir>/scripts/windows_mode.py probe --path <project-root> --shell <powershell|cmd|bash|wsl>
```

On Windows, prefer `py -3` when `python` is unavailable. Inside WSL, use `python3`. If the active shell is genuinely unknown, omit `--shell` and treat an `unknown` result as unresolved rather than guessing.

4. Read repository guidance, lockfiles, scripts, and CI before selecting a shell or package command.
5. Keep the current environment unless the project clearly requires another one or the user chooses a switch.

## Set the environment boundary

Classify the working session as one of:

- **Native Windows + PowerShell**: use PowerShell syntax, Windows paths, and Windows-native tools.
- **Native Windows + cmd.exe**: use cmd syntax only when that is the active shell.
- **Native Windows + Git Bash/MSYS2**: use POSIX-like syntax but preserve Windows executable and path behavior.
- **WSL**: use Linux commands, Linux paths, and toolchains installed inside that WSL distribution.
- **Unclear or mixed**: pause command execution, report the conflicting evidence, and ask one product-level question if inspection cannot resolve it.

Do not switch between native Windows and WSL merely because a command failed. A switch changes the filesystem, environment variables, credentials, package caches, installed tools, permissions, file watching, and process ownership.

## Check commands before execution

Check setup, build, test, dev-server, package-manager, filesystem, and process commands:

```text
python <skill-dir>/scripts/windows_mode.py check --shell <powershell|cmd|bash|wsl> --cwd <project-root> -- <command>
```

Interpret the result:

- `safe`: no known shell or path mismatch was found. Normal task safeguards still apply.
- `review`: the command may depend on a version, alias, quoting rule, or mixed filesystem. Inspect it before running.
- `blocked`: do not run the command in the stated environment. Rewrite it for the active shell or deliberately change environments first.

The checker is a compatibility guardrail, not a security sandbox.

## Command rules

- Prefer project scripts such as `npm test`, `pnpm lint`, `gradlew.bat`, or checked-in wrappers over manually translating their internals.
- Use `rg` for search when available. It behaves consistently across supported environments.
- In PowerShell, use `$env:NAME`, `Get-ChildItem`, `Get-Content`, `Remove-Item`, `New-Item`, `Get-Command`, and `$LASTEXITCODE` where their behavior matters.
- In cmd.exe, use `%NAME%` and cmd-native chaining. Do not paste PowerShell cmdlets into cmd.
- In WSL, use Linux paths and Linux-installed tools. Run Windows executables from WSL only when the task specifically needs a Windows resource.
- Treat Git Bash/MSYS2 as its own environment. POSIX-looking syntax does not make its paths, signals, file locks, or executable resolution identical to Linux.
- Never combine a Windows path and a WSL-only command without explicit conversion and a reason.
- Quote paths with spaces. Use literal-path operations in PowerShell when wildcard expansion is unintended.
- Preserve the command's real exit code. Do not infer success from printed text alone.

## Files, Git, and line endings

- Inspect `.gitattributes`, `.editorconfig`, and existing file endings before changing Git line-ending settings.
- Do not run repository-wide line-ending conversion as a casual fix.
- Do not alter global `core.autocrlf` for one project.
- Treat case-only renames carefully on case-insensitive filesystems. Verify the final Git diff.
- Avoid editing WSL project files through a Windows UNC path during build or test work. Prefer running the agent and tools inside WSL for projects stored in the WSL filesystem.
- Do not move a project between NTFS and the WSL filesystem without the user's approval.

## Processes, ports, and locked files

- Identify the owning process before stopping it. Do not kill all Node, Python, Java, or browser processes.
- Reuse an existing dev server when it belongs to the project and is healthy.
- On Windows, expect open files and directories to resist deletion. Stop the exact owning process, verify it exited, then retry the narrow operation.
- Do not delete lockfiles, SQLite sidecars, build directories, or package caches until live-process ownership and project impact are known.
- Use the active environment to inspect ports. A Windows process and a WSL process may expose the same port through different ownership paths.

## WSL boundary

Before using WSL, establish all four facts:

1. The selected distribution.
2. Whether the project lives under Linux storage, `/mnt/<drive>`, or a Windows UNC view.
3. Whether Git and the language runtime resolve inside WSL or on Windows.
4. Which environment owns the dev server, container engine, credentials, and generated files.

If those facts conflict, stop and present the smallest choice in visible terms, such as:

```text
The project files are inside WSL, but tests are currently running with Windows Node.js.

Use WSL Node.js: matches the project filesystem and Linux CI.
Use Windows Node.js: keeps the current Windows toolchain but may break paths and file watching.
```

Do not ask the user to choose between implementation details without stating the visible consequence.

## Finish the task

Verify with commands from the same environment used to make the change. Report:

```text
Environment: <native Windows/WSL/Git Bash and shell>
Verified: <focused checks that passed>
Deferred: <checks not run and why>
Windows note: <only a real portability, lock, path, or line-ending concern>
```

Do not claim cross-platform support from a Windows-only check. Do not claim Windows support from a Linux-only CI run.

## Limits

This mode cannot repair product-level Windows or WSL bugs, make Linux-only dependencies work natively, remove organizational restrictions, or prevent every third-party tool from mishandling paths, signals, file locks, or line endings.
