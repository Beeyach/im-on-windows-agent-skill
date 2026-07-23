# I'm on Windows

**A Windows-aware Agent Skill for Claude Code and Codex.** It keeps AI coding agents from mixing PowerShell, cmd.exe, Git Bash, WSL, Windows paths, Linux paths, and toolchains during normal project work.

If an AI coding assistant keeps giving you Bash commands on Windows, rewrites `C:\...` as `/mnt/c/...`, runs Windows Node.js against a WSL project, creates CRLF-only diffs, or kills every Node process to free one port, this skill changes its working rules before those mistakes happen.

## What changes

- Detects native Windows, PowerShell, cmd.exe, Git Bash/MSYS2, and WSL
- Keeps paths, package managers, language runtimes, and process commands in one environment
- Checks proposed commands for shell and path mismatches
- Blocks common Bash-in-PowerShell, PowerShell-in-Bash, and Windows-path-in-WSL mistakes
- Flags WSL projects accessed through Windows UNC paths
- Protects against casual global line-ending changes and broad process killing
- Converts common Windows drive, WSL mount, and WSL UNC path forms
- Requires verification from the same environment used for the change

It does not install WSL, change shells, modify Git settings, move projects, kill processes, or execute checked commands.

## Install

Clone or download the repository, then run:

```text
python install.py --agent both
```

Install for one agent:

```text
python install.py --agent claude
python install.py --agent codex
```

Update an existing installation:

```text
python install.py --agent both --force
```

The installer uses the current personal skill locations:

- Claude Code: `~/.claude/skills/im-on-windows`
- Codex: `~/.agents/skills/im-on-windows`

## Use

Ask naturally:

```text
I'm on Windows. Fix the failing build.
```

Or invoke it explicitly:

```text
Use $im-on-windows while setting up this project.
```

The agent probes the active environment, follows the repository's existing scripts, checks commands before execution, and reports which environment performed verification.

## Helper

Probe a project:

```text
python skill/scripts/windows_mode.py probe --path . --shell powershell
```

Check a command:

```text
python skill/scripts/windows_mode.py check --shell powershell --cwd C:\work\app -- "rm -rf dist"
```

Convert a path:

```text
python skill/scripts/windows_mode.py path --to wsl "C:\Users\Ary\project"
```

The checker exits with `0` for safe, `1` for review, `2` for blocked, and `64` when no command is supplied.

## Scope

This is proactive daily behavior. It is deliberately narrower than a Windows repair toolkit. For deep diagnosis after an agent session is already broken, see [Windows Claude Code Doctor](https://github.com/IliaMalkin/windows-claude-code-doctor), which includes specialized PowerShell diagnostics for ports, file handles, SQLite locks, runtime mismatches, and line endings.

## Test

```text
python -m unittest discover -s tests -v
```

The public matrix runs on Windows, macOS, and Linux with Python 3.10 and 3.13.

## Search terms

Windows AI coding assistant, Claude Code Windows skill, Codex Windows skill, PowerShell Agent Skill, WSL path mismatch, Bash commands failing on Windows, Git Bash versus WSL, Windows file locking, CRLF Git diff, native Windows coding agent, vibe coding on Windows.

## License

MIT
