# Authentication Configuration (`config.properties`)

This document explains how authentication for **user -> MCP** works, how it is configured, and how each mode affects runtime behavior.

It also documents how clients should send credentials to the MCP server.

---

## Goals

Supported authentication modes:

1. `knox` (existing implementation, unchanged)
2. `none` (local laptop testing only)
3. `basic_static` (**default**)
4. `ldap`
5. `nifi_integrated` (NiFi token + user lookup + optional group check)

Design constraints:

- **Fail closed** (`mcp.auth.fail_open=false`): backend errors deny access.
- `none` mode only allowed in local environment.
- HTTP outcomes:
  - Invalid / missing credentials -> **401**
  - Authenticated but not allowed (e.g. missing required group) -> **403**

---

## Core Configuration

```properties
app.environment=local
mcp.auth.mode=basic_static
mcp.auth.fail_open=false
mcp.authz.group_check.enabled=false
mcp.authz.required_group=
```

### Keys

- `app.environment`: `local|dev|test|prod`
- `mcp.auth.mode`: `basic_static|none|knox|ldap|nifi_integrated`
- `mcp.auth.fail_open`: must be `false`
- `mcp.authz.group_check.enabled`: enables group enforcement
- `mcp.authz.required_group`: group name required if group check is enabled

---

## Client -> MCP: How to send authentication

For `basic_static`, clients authenticate using HTTP Basic credentials:

1. Build `username:password`
2. Base64 encode it
3. Send `Authorization: Basic <encoded>`

Example:

```bash
printf 'admin:change_me' | base64
```

Result:

```text
YWRtaW46Y2hhbmdlX21l
```

Final header:

```text
Authorization: Basic YWRtaW46Y2hhbmdlX21l
```

### Important current implementation note

Incoming auth is enforced by MCP tools.

Tools support two input paths:

- Explicit `authorization` tool argument (for example `get_nifi_version(authorization=...)`)
- Automatic fallback to the transport `Authorization` header (for example headers configured in LM Studio MCP server config)

If both are present, the explicit tool argument is used.

Example tool argument payload:

```json
{
  "authorization": "Basic YWRtaW46Y2hhbmdlX21l"
}
```

### LM Studio network config example

`examples/mcp.sjon` includes:

```json
{
  "mcpServers": {
    "nifi-mcp-server": {
      "url": "http://127.0.0.1:3030/sse",
      "headers": {
        "Authorization": "Basic YWRtaW46Y2hhbmdlX21l"
      }
    }
  }
}
```

With this server behavior, LM Studio header-based configuration should work without passing `authorization` in every tool call.

### Quick validation without NiFi

Enable debug auth tool exposure only during this test:

```bash
MCP_AUTH_EXPOSE_TEST_TOOL=true python -m nifi_mcp_server.server
```

Before testing NiFi-dependent tools, validate auth only with:

```text
Please call authenticate_request and show me the result.
```

Expected success fields:

- `ok: true`
- `principal.username: admin`

If result is `401` with `Missing or invalid Basic Authorization header`, the client is not forwarding the configured Authorization header on tool calls.

By default, `authenticate_request` is not exposed to avoid auto-call loops in some MCP clients.

---

## Mode: `basic_static` (default)

```properties
mcp.auth.mode=basic_static
mcp.auth.basic.username=admin
mcp.auth.basic.password=change_me
```

Behavior:

- Expects HTTP Basic auth on incoming request.
- Compares credentials against configured fixed username/password.
- Success -> authenticated user.
- Wrong credentials -> `401`.

Use case:

- Local/simple deployment with a fixed credential pair.

---

## Mode: `none` (local only)

```properties
mcp.auth.mode=none
app.environment=local
mcp.auth.none.allow_in_local_only=true
```

Behavior:

- Bypasses authentication entirely.
- Returns synthetic local principal (for testing only).
- If environment is not `local`, startup must fail.

Security impact:

- No identity validation.
- Never use outside local testing.

---

## Mode: `knox`

```properties
mcp.auth.mode=knox
mcp.auth.knox.enabled=true
# existing knox keys remain unchanged in your project
```

Behavior:

- Uses existing Knox authentication path.
- Implementation should be wrapped/adapted, not rewritten.
- Backend errors -> deny (`401`) due to fail-closed.

---

## Mode: `ldap`

```properties
mcp.auth.mode=ldap
mcp.auth.ldap.url=ldaps://ldap.example.local:636
mcp.auth.ldap.bind_dn=cn=svc_mcp,ou=svc,dc=example,dc=local
mcp.auth.ldap.bind_password=secret
mcp.auth.ldap.user_base_dn=ou=people,dc=example,dc=local
mcp.auth.ldap.user_filter=(uid={username})

mcp.auth.ldap.group_base_dn=ou=groups,dc=example,dc=local
mcp.auth.ldap.group_filter=(member={user_dn})

mcp.auth.ldap.timeout_seconds=5
mcp.auth.ldap.tls.verify=true
mcp.auth.ldap.tls.ca_file=/etc/nifi-mcp/ldap-ca.pem
```

Behavior:

- Extracts incoming Basic credentials.
- Validates user against LDAP (bind/search flow).
- Optional group retrieval can feed authorization.
- Timeout/network/TLS errors -> deny (`401`).

---

## Mode: `nifi_integrated`

Supports your requested flow:
1. `POST /access/token`
2. resolve current user
3. `GET /tenants/users/{id}` to obtain groups
4. optional MCP-side group check

```properties
mcp.auth.mode=nifi_integrated
mcp.auth.fail_open=false

mcp.auth.nifi.base_url=https://nifi.example.local:9443
mcp.auth.nifi.timeout_seconds=8

mcp.auth.nifi.tls.verify=true
mcp.auth.nifi.tls.ca_file=/etc/nifi-mcp/ca.pem
mcp.auth.nifi.tls.client_cert_file=/etc/nifi-mcp/client.crt
mcp.auth.nifi.tls.client_key_file=/etc/nifi-mcp/client.key

mcp.auth.nifi.token_endpoint=/nifi-api/access/token

mcp.auth.nifi.current_user_endpoint=/nifi-api/access/current-user
mcp.auth.nifi.current_user_username_field=identity
mcp.auth.nifi.current_user_id_field=id

mcp.auth.nifi.user_by_id_endpoint_template=/nifi-api/tenants/users/{id}
mcp.auth.nifi.groups_field=userGroups
mcp.auth.nifi.groups_field_fallback=component.userGroups
mcp.auth.nifi.groups_missing_is_denied=true

mcp.authz.group_check.enabled=true
mcp.authz.required_group=nifi-mcp-users
```

### NiFi 1.x / 2.x compatibility

Endpoint paths can vary between versions/setup. Keep all paths configurable as shown above.  
If current-user or tenant payload shape differs, adjust field keys:
- `mcp.auth.nifi.current_user_username_field`
- `mcp.auth.nifi.current_user_id_field`
- `mcp.auth.nifi.groups_field` / fallback

### Important operational note

If the authenticated user/token is not allowed to call tenant endpoints, group resolution may fail with forbidden:
- this should return **403** (authenticated but not permitted for required authorization path).

---

## HTTP Response Semantics

- **401 Unauthorized**
  - Missing/invalid Basic header
  - Invalid credentials
  - Auth backend unavailable (timeout/TLS/network)
  - Any auth backend technical failure (fail-closed)

- **403 Forbidden**
  - Authenticated identity is valid, but not authorized by policy
  - Required group missing
  - Access to group resolution endpoint denied in a way that prevents authorization completion

---

## MCP -> NiFi Transport/Auth (separate concern)

This is independent from user->MCP auth mode and should remain separately configurable.

```properties
nifi.tls.cert_file=/etc/nifi-mcp/client.crt
nifi.tls.key_file=/etc/nifi-mcp/client.key
knox.verify.ssl=true
knox.ca.bundle=/etc/nifi-mcp/ca.pem

nifi.knox.enabled=false
```

---

## Recommended Defaults

For your local target:

```properties
app.environment=local
mcp.auth.mode=basic_static
mcp.auth.fail_open=false
mcp.authz.group_check.enabled=false
```

For integration tests with NiFi identity:

```properties
app.environment=local
mcp.auth.mode=nifi_integrated
mcp.auth.fail_open=false
mcp.authz.group_check.enabled=true
mcp.authz.required_group=nifi-mcp-users
```

---

## Troubleshooting Checklist

1. `401` for all requests:
   - Verify client sends Basic header.
   - Check token endpoint path and NiFi base URL.
   - Check TLS CA/cert/key paths and permissions.

2. `403` in `nifi_integrated`:
   - Confirm group exists and exact spelling.
   - Confirm tenants endpoint and response JSON fields.
   - Confirm caller/token has rights to read user details/groups.

3. startup config failure:
   - Ensure required keys for selected `mcp.auth.mode` are present.
   - Ensure `none` mode only in `app.environment=local`.