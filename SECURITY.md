# Security policy

## Reporting

Do not open a public issue for a vulnerability that could expose secrets, replace unrelated directories, or run an unsafe command. Report it privately through GitHub's security advisory feature.

## Boundary

`windows_mode.py` inspects paths, environment details, executable locations, and command text. It does not execute checked commands. Its output can contain local usernames and paths, so review it before posting publicly.

The checker is a compatibility guardrail. It is not a command sandbox, malware scanner, or substitute for agent permissions.
