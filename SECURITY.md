# Security policy

## What this software is

Pump Station Zero Community is a local practice tool. It runs a simulated pump station, a bounded Modbus TCP server and an HTTP interface on your own computer. It controls no physical equipment and is not production control software.

## Intended deployment

- **Loopback only.** The server binds to 127.0.0.1 and has no option to bind elsewhere or to target another host.
- **Local users are trusted.** Anyone who can run software on the same computer can reach the listener. Loopback is not isolation from a malicious local user.
- **No TLS.** The HTTP listener is plain HTTP on loopback and does not claim otherwise.
- **Do not expose it.** Do not publish the listener through a reverse proxy, tunnel or port forward. Hosting it for other people needs a separately designed and reviewed authentication and transport perimeter, which this repository does not provide.

## Built-in protections

- Each browser gets its own station, bound to an HttpOnly, SameSite=Strict session cookie; another session's reports are not reachable.
- Host and Origin checks block ordinary cross-site requests to the controls.
- Request bodies, sessions (8), saved reports (8 per station), retained events (256) and HMI history (two hours) are bounded.
- HTTP controls are a fixed set of actions. They accept no address, port, register or command value.
- Simulator interlocks and atomic multi-register writes reject unsafe or partial changes as a whole.
- Report and HMI output is escaped.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through this repository's private vulnerability reporting, not in a public issue. Include the version or commit, the steps to reproduce and what you expected to happen.

## Supported versions

Only the latest commit of this repository is supported.
