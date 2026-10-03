# ADR-0005: GUI server is loopback-only and token-authenticated

- **Status:** Proposed · **Date:** 2026-10-02 · **Specs:** [02 § 8](../specs/02-safety-and-security.md#8-gui-server-hardening), [05 § 2](../specs/05-cli-and-api.md#2-http-api-v2) · **Fixes:** B03, B04, B12–B14, B26, B27

## Context
The v0.1 server binds every interface, sends `Access-Control-Allow-Origin: *`, has no authentication, and falls back to serving every file in the target folder. Any web page the user visits can drive it with `fetch`, and so can anyone on the same network. The API can move arbitrary files (B01/B02). Effectively, this is a remote file-manipulation service.

## Decision
- Bind `127.0.0.1` (and `::1`) only. Any other host requires an explicit, scary flag.
- Generate a per-session random token. Deliver it through the URL fragment when the browser opens, and require it as a Bearer header on every API call.
- Strict `Host` allow-list (against DNS rebinding) and an `Origin` check on mutating requests. No CORS at all.
- An explicit route table. Static files only from vendored package assets, with a strict CSP.
- `ThreadingHTTPServer` and a `JobManager` that allows one mutating job per Root.

## Consequences
- **Positive:** a malicious page or a LAN peer cannot reach the API. Combined with the server-side containment from B01, even a compromised tab cannot move files outside the Root.
- **Negative:** the user cannot bookmark the URL across restarts, because the token changes each session. `serve` prints a fresh link. Third-party scripts that used the v1 API need the token (`serve --print-token`).

## Alternatives considered
- **Cookie-based session:** needs CSRF handling and SameSite caveats. A header token is simpler and cannot be sent by a browser automatically.
- **Unix domain socket or native app:** browsers can't connect to a Unix socket directly, and a native app is out of scope (it belongs to the GUI redesign).
