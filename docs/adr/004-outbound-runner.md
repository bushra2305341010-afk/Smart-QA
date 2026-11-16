# ADR-004: Runner connects outbound only over mTLS

**Status:** Accepted · **Date:** 2026-11-16

## Context
Apps under test live on private networks; companies will not open inbound ports.

## Decision
The runner runs inside the team network and opens an outbound WSS connection with a client certificate.

## Consequences
No firewall changes; strong runner identity. Need cert issuance and rotation.

## Alternatives considered
Inbound agent; public tunnel only.
