# Local Setup Guide (venv, install, run)

This guide shows how to:

1. Create and activate a Python virtual environment (`venv`)
2. Install dependencies
3. Verify/compile Python files
4. Run the NiFi MCP Server

---

## Prerequisites

- Python **3.10+**
- `git`
- macOS/Linux shell (commands below)

---

## 1) Clone repository

```bash
git clone https://github.com/mobidirk/NiFi-MCP-Server.git
cd NiFi-MCP-Server
```

---

## 2) Create and activate virtual environment

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

You should now see `(.venv)` in your shell prompt.

### Windows (PowerShell)

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
```

---

## 3) Upgrade pip and install project

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Optional dev tools (pytest/ruff) with uv:
```bash
uv sync --dev
```

---

## 4) Configure `config.properties`

Configuration is loaded in this order:

1. Environment variables
2. `config.properties` in current working directory
3. `src/nifi_mcp_server/config.properties` (package default)

You can also force a specific file via:

```bash
export CONFIG_PROPERTIES_PATH=/absolute/path/to/config.properties
```

Minimal example for local tests:

```properties
app.environment=local
mcp.transport=sse
mcp.host=127.0.0.1
mcp.port=3030

mcp.auth.mode=basic_static
mcp.auth.fail_open=false
mcp.auth.basic.username=admin
mcp.auth.basic.password=change_me

NIFI_API_BASE=https://<your-nifi>/nifi-api
KNOX_TOKEN=<your-token>
nifi.readonly=true
```

> If you use `mcp.auth.mode=none`, it is only allowed in `app.environment=local`.

Transport note:

- `mcp.transport=stdio` is for desktop MCP clients and does not open a TCP port.
- `mcp.transport=sse` or `streamable-http` opens an HTTP listener using `mcp.host` and `mcp.port`.

---

## 5) Compile/check Python source

This checks syntax/import compilation:

```bash
python -m compileall src
```

If successful, no fatal errors are shown.

---

## 6) Run the server

### Module mode

```bash
python -m nifi_mcp_server.server
```

### Script entry point (installed via pyproject)

```bash
run-server
```

### Verify listener with curl (SSE)

If `mcp.transport=sse`, run:

```bash
curl -i --max-time 3 http://127.0.0.1:3030/sse
```

Expected:

- `HTTP/1.1 200 OK`
- `content-type: text/event-stream`
- `event: endpoint` with a `/messages/?session_id=...` URL

The timeout is expected and normal because SSE keeps the connection open.

---

## 7) Common troubleshooting

## Error: `ModuleNotFoundError: No module named 'tenacity'`
Install dependencies in active venv:

```bash
python -m pip install -e .
```

Then verify:

```bash
python -m pip show tenacity
which python
```

Both should refer to your `.venv`.

## Wrong interpreter / mixed environments
Always run with activated `.venv`:

```bash
source .venv/bin/activate
which python
```

Expected path contains `/.venv/bin/python`.

## SSL / cert issues against NiFi
Set custom CA bundle in config:

```properties
knox.verify.ssl=true
knox.ca.bundle=/path/to/ca.pem
```

For mTLS MCP->NiFi:
```properties
nifi.tls.cert_file=/path/client.crt
nifi.tls.key_file=/path/client.key
```

---

## 8) Deactivate venv when done

```bash
deactivate
```

---

## Quick command summary

```bash
git clone https://github.com/mobidirk/NiFi-MCP-Server.git
cd NiFi-MCP-Server
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m compileall src
python -m nifi_mcp_server.server
```