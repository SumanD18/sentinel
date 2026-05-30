# Security Policy

## Supported versions

Sentinel is pre-1.0. Security fixes land on `main` and the latest release.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Instead, use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository (Security → Report a vulnerability), or email the maintainers
listed in the repository's GitHub profile.

We aim to acknowledge reports within 72 hours and to ship a fix or mitigation
within 30 days, coordinating disclosure with you.

## Handling sensitive data

Sentinel captures prompts and responses, which may contain secrets or PII. By
design:

- **PII redaction runs in your process** before any data is exported
  (`SENTINEL_REDACT_PII=true`, on by default).
- You can disable payload capture entirely with `SENTINEL_CAPTURE_CONTENT=false`
  to record only metadata.
- The collector and dashboard are **self-hosted** - no trace data is sent to any
  third party.
- Enable API-key auth on the collector in any shared environment
  (`SENTINEL_API_KEYS`).

If you find a way to bypass redaction or leak captured payloads, that is a
security issue - please report it as above.
