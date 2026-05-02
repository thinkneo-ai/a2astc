# Changelog

All notable changes to A2ASTC are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-01

### Added

- Initial release of A2ASTC specification (20 sections)
- Reference implementation (`thinkneo-a2astc` on PyPI)
- Team detection from bidirectional communication patterns (Section 5)
- Versioned Team Manifest with capability aggregation and safety classification (Section 6)
- Five orthogonal audit signal families: Topology, Semantic, Privilege, Side-Channel, Cascade (Section 7)
- Synchronous Team Compliance Gate with five verdict levels: ALLOW, WARN, THROTTLE, ISOLATE, TERMINATE (Section 8)
- Graduated intervention layer with cooldowns and token-bucket throttling (Section 9)
- SHA-256 hash-chained tamper-evident audit trail with 15 event types (Section 10)
- Four transport adapters: A2A JSON-RPC, A2A gRPC, MCP Bridge, Generic (Section 11)
- Three conformance levels: Detection, Audit, Full Compliance (Section 12)
- Team Compliance Kit (TCK) with 15 adversarial fixtures (Section 13)
- Five JSON Schema definitions (draft 2020-12) (Section 15)
- 238 tests passing
- Benchmark suite for gate evaluation latency

[0.1.0]: https://github.com/thinkneo-ai/a2astc/releases/tag/v0.1.0
