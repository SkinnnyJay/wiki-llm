# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through [GitHub Security Advisories](https://github.com/SkinnnyJay/wiki-llm/security/advisories/new). Do not open a public issue until maintainers have had a reasonable opportunity to investigate and release a fix.

Include affected versions, reproduction steps or a proof of concept, impact, and any suggested mitigation. Maintainers will acknowledge reports and coordinate disclosure through the advisory.

## Scope

See the [threat model](docs/THREAT-MODEL.md) for supported trust boundaries and residual risks. llm-wiki is a local-first application; its security controls protect the application and its configured vault/MCP boundaries. They are not a replacement for malware scanning, dependency scanning, or broader host and network security controls.
