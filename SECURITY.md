# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Email security@akiva.com with:
- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Affected version(s)

We will acknowledge receipt within 48 hours and provide a triage assessment within 7 business days.

## Disclosure Policy

We follow coordinated disclosure. We ask that you give us 90 days to address the issue before public disclosure.

## Scope

### In Scope

- Code in the `src/` directory
- CLI argument parsing and file handling
- Contract inference, validation, and drift detection logic
- Docker image configuration
- CI/CD pipeline security (workflow injection, secret exposure)

### Out of Scope

- Issues in upstream dependencies (report to the upstream project)
- Issues requiring physical access to the machine running the tool
- Social engineering attacks

## Security Considerations

This tool processes local files only. It has zero runtime dependencies and does not make network connections. Key security properties:

- **No eval/exec:** No dynamic code execution of any kind
- **No shell commands:** No subprocess or os.system calls
- **No network access:** Purely file-based I/O
- **Path validation:** All file paths are resolved to absolute paths before access
- **Non-root Docker:** Container runs as unprivileged user
