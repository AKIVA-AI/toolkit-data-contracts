# Security policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 1.0.x   | Yes       |
| < 1.0   | No        |

Security fixes are released as patch versions of the latest minor release.

## Reporting a vulnerability

Please do not report security problems in a public issue, pull request or
discussion. Report them privately through GitHub: open this repository's
**Security** tab and choose **Report a vulnerability**
(<https://github.com/AKIVA-AI/toolkit-data-contracts/security/advisories/new>). Include:

- what the problem is and its impact;
- steps or input files to reproduce it;
- the affected version or commit.

We aim to acknowledge a report within 7 days and ask for up to 90 days to
release a fix before public disclosure. We credit reporters who want to be
credited.

## Scope

In scope: code in `src/`, CLI argument and file handling, the Docker image,
and the CI workflows. Issues in upstream projects should be reported upstream.

## Security properties

This tool reads and writes local files only. It has no runtime dependencies
and makes no network connections.

- No `eval`/`exec` and no subprocess or shell calls.
- JSON input is parsed strictly (`NaN`/`Infinity` are rejected).
- Output paths containing `..` are refused.
- The Docker image runs as a non-root user.
