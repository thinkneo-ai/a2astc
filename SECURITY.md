# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | Yes                |

## Reporting a Vulnerability

If you discover a security vulnerability in A2ASTC, **please do not open a public issue.**

Instead, report it via email to: **security@thinkneo.ai**

Include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a detailed response within 5 business days. We will coordinate disclosure with you.

## Scope

The following are in scope for security reports:

- Hash chain integrity bypass
- Gate evaluation bypass (delivering messages without gate check)
- Signal evasion techniques not covered by existing TCK fixtures
- Audit trail tampering
- Configuration injection
- Identity spoofing via adapters

## Out of Scope

- Individual agent safety (that is the provider's responsibility)
- Network-level security (TLS configuration, authentication)
- Denial of service via legitimate high message volume

## Security Design

See [SPEC.md Section 16](SPEC.md#16-security-considerations) for the full threat model and mitigations.
