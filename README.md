# NiFi MCP Server (via Knox)

Model Context Protocol server providing selectable read and write access to Apache NiFi via Apache Knox.

**Works with both NiFi 1.x and 2.x** - automatic version detection and adaptation.

![](/screenshots/Nifi-meet-mcp.png)

## Features

- **Automatic version detection** - Detects NiFi 1.x vs 2.x and adapts behavior
- **Knox authentication** - Supports Bearer tokens, cookies, and passcode tokens for CDP deployments
- **Read-only by default** - Safe exploration of NiFi flows and configuration
- **Intelligent flow building** - Pattern recognition and requirements gathering for complex flows
- **24 read-only MCP tools** for exploring NiFi:
  - `get_nifi_version()` - Version and build information
  - `get_root_process_group()` - Root process group details
  - `list_processors(process_group_id)` - List processors in a process group
  - `list_connections(process_group_id)` - List connections in a process group
  - `get_bulletins(after_ms?)` - Recent bulletins and alerts
  - `list_parameter_contexts()` - Parameter contexts
  - `get_controller_services(process_group_id?)` - Controller services
  - `get_processor_types()` - Available processor types for flow building
  - `search_flow(query)` - Search for components in the flow
  - `get_connection_details(connection_id)` - Detailed connection information
  - `get_processor_details(processor_id)` - Detailed processor configuration
  - `list_input_ports(process_group_id)` - Input ports for a process group
  - `list_output_ports(process_group_id)` - Output ports for a process group
  - `get_processor_state(processor_id)` - Quick processor state check
  - `check_connection_queue(connection_id)` - Queue size (flowfiles + bytes)
  - `get_flow_summary(process_group_id)` - Flow statistics and health overview
  - `analyze_flow_build_request(user_request)` - Intelligent pattern recognition and requirements gathering
  - `get_parameter_context_details(context_id)` - Get parameter context with all parameters
  - `get_flow_health_status(process_group_id)` - Comprehensive flow health check (processors, services, connections, errors)
  - `find_controller_services_by_type(process_group_id, service_type)` - Search for existing controller services by type (prevents 409 conflicts)
  - `check_configuration()` - Validate current environment configuration
  - `get_setup_instructions()` - Interactive setup guidance for NiFi MCP Server
  - `get_best_practices_guide()` - Best practices for building NiFi flows
  - `get_recommended_workflow(flow_type)` - Step-by-step guidance for common flow patterns
- **42 write operations** (when `NIFI_READONLY=false`):
  - `start_processor(processor_id, version)` - Start a processor
  - `stop_processor(processor_id, version)` - Stop a processor
  - `create_processor(...)` - Create a new processor
  - `update_processor_config(...)` - Update processor configuration
  - `delete_processor(processor_id, version)` - Delete a processor
  - `create_connection(...)` - Connect components
  - `delete_connection(connection_id, version)` - Delete a connection
  - `empty_connection_queue(connection_id)` - Empty flowfiles from queue (⚠️ data loss)
  - `create_controller_service(pg_id, service_type, name)` - Create controller services (DBCPConnectionPool, RecordWriters, etc.)
  - `update_controller_service_properties(service_id, version, properties)` - Configure service properties
  - `get_controller_service_details(service_id)` - Get service configuration (read-only but listed here for context)
  - `delete_controller_service(service_id, version)` - Remove controller services
  - `enable_controller_service(service_id, version)` - Enable a controller service
  - `disable_controller_service(service_id, version)` - Disable a controller service
  - `create_process_group(parent_id, name, x, y)` - Create process groups (folders) for organizing flows
  - `update_process_group_name(pg_id, version, name)` - Rename process groups
  - `delete_process_group(pg_id, version)` - Remove empty process groups
  - `create_input_port(pg_id, name, x, y)` - Create input ports for inter-process-group communication
  - `create_output_port(pg_id, name, x, y)` - Create output ports for inter-process-group communication
  - `update_input_port(port_id, version, name)` - Rename input ports
  - `update_output_port(port_id, version, name)` - Rename output ports
  - `delete_input_port(port_id, version)` - Remove input ports
  - `delete_output_port(port_id, version)` - Remove output ports
  - `create_parameter_context(name, description, parameters)` - Create parameter contexts for environment-specific config
  - `update_parameter_context(context_id, version, ...)` - Update parameter contexts
  - `delete_parameter_context(context_id, version)` - Remove parameter contexts
  - `start_input_port(port_id, version)` - Start input port to enable data flow
  - `stop_input_port(port_id, version)` - Stop input port
  - `start_output_port(port_id, version)` - Start output port to enable data flow
  - `stop_output_port(port_id, version)` - Stop output port
  - `apply_parameter_context_to_process_group(pg_id, pg_version, context_id)` - Apply parameter context to enable #{param} usage
  - `start_all_processors_in_group(pg_id)` - Bulk start all processors at once (10-15x faster!)
  - `stop_all_processors_in_group(pg_id)` - Bulk stop all processors at once  
  - `enable_all_controller_services_in_group(pg_id)` - Bulk enable all services at once
  - `terminate_processor(processor_id, version)` - Force-terminate stuck processor (last resort)
  - `start_new_flow(flow_name, flow_description)` - Smart flow builder that automatically creates process groups and enforces best practices

## Quick Start

### For CDP NiFi deployments

Your NiFi API base URL will typically be:
```
https://<your-nifi-host>/nifi-2-dh/cdp-proxy/nifi-app/nifi-api
```

Get your Knox JWT token from the CDP UI and use it with the configurations below.

## Setup

### Option 1: Claude Desktop (Local)

1. **Clone and install:**
   ```bash
   git clone https://github.com/kevinbtalbert/nifi-mcp-server.git
   cd nifi-mcp-server
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Configure Claude Desktop** - Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
   ```json
    {
      "mcpServers": {
        "nifi-mcp-server": {
          "command": "/FULL/PATH/TO/NiFi-MCP-Server/.venv/bin/python",
          "args": [
            "-m",
            "nifi_mcp_server.server"
          ],
          "env": {
            "MCP_TRANSPORT": "stdio",
            "NIFI_API_BASE": "https://nifi-2-dh-management0.yourshere.cloudera.site/nifi-2-dh/cdp-proxy/nifi-app/nifi-api",
            "KNOX_TOKEN": "<your_knox_bearer_token>",
            "NIFI_READONLY": "true"
          }
        }
      }
    }
   ```

3. **Restart Claude Desktop** and start asking questions about your NiFi flows!

### Option 2: Direct Installation (Cloudera Agent Studio)

For use with Cloudera Agent Studio, use the `uvx` command:

```json
{
  "mcpServers": {
    "nifi-mcp-server": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/kevinbtalbert/nifi-mcp-server@main",
        "run-server"
      ],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "NIFI_API_BASE": "https://nifi-2-dh-management0.yourshere.cloudera.site/nifi-2-dh/cdp-proxy/nifi-app/nifi-api",
        "KNOX_TOKEN": "<your_knox_bearer_token>",
        "NIFI_READONLY": "true"
      }
    }
  }
}
```

### Quick curl smoke test (SSE transport)

When `mcp.transport=sse`, verify the listener and SSE endpoint:

```bash
curl -i --max-time 3 http://127.0.0.1:3030/sse
```

Expected result:

- HTTP `200 OK`
- `content-type: text/event-stream`
- an SSE `event: endpoint` line with a `/messages/?session_id=...` URL

Note: this command times out after 3 seconds by design (`--max-time 3`) to avoid hanging on an open event stream.

### Configure client authentication to the MCP server

This project supports incoming auth modes (`basic_static`, `none`, `knox`, `ldap`, `nifi_integrated`) via `mcp.auth.*` settings.

Current behavior in this codebase:

- Incoming auth is checked by MCP tools.
- Tools accept an explicit `authorization` argument, and now also fall back to the transport request `Authorization` header automatically.

For `basic_static`, set these in your config:

```properties
mcp.auth.mode=basic_static
mcp.auth.basic.username=admin
mcp.auth.basic.password=change_me
```

Create a Basic header value:

```bash
printf 'admin:change_me' | base64
```

Use the returned value as:

```text
Basic <base64(username:password)>
```

Example tool call argument:

```json
{
  "authorization": "Basic YWRtaW46Y2hhbmdlX21l"
}
```

LM Studio network example (`examples/mcp.sjon`) includes an `Authorization` header and should work without manually passing `authorization` in each tool call.

### No-NiFi smoke test (auth only)

Enable the auth test tool only for this smoke test:

```bash
MCP_AUTH_EXPOSE_TEST_TOOL=true python -m nifi_mcp_server.server
```

Then ask your client:

To verify MCP authentication wiring before configuring a real NiFi backend, ask your client:

```text
Please call authenticate_request and show me the result.
```

Expected success response includes:

- `ok: true`
- `principal.username: admin`

If you get `401 Missing or invalid Basic Authorization header`, your MCP client is not sending the configured `Authorization` header on tool requests.

Note: `authenticate_request` is hidden by default to prevent some MCP clients from repeatedly auto-calling it.

## Configuration Options

Configuration is loaded with this precedence:

1. Environment variables
2. `config.properties` in current working directory
3. `src/nifi_mcp_server/config.properties`

You can also set `CONFIG_PROPERTIES_PATH` to point at a specific properties file.

### Core transport settings

```properties
mcp.transport=sse
mcp.host=127.0.0.1
mcp.port=3030
```

Supported transports:

- `stdio`: for MCP desktop clients (no TCP listener)
- `sse`: HTTP listener (default in sample config)
- `streamable-http`: HTTP MCP transport

If you try `telnet localhost 3030` while using `stdio`, connection refused is expected.

### Core NiFi connectivity settings

```properties
NIFI_API_BASE=https://<your-nifi>/nifi-api
KNOX_TOKEN=<your-token>
nifi.readonly=true
knox.verify.ssl=true
knox.ca.bundle=
```

\* Either `NIFI_API_BASE` or `knox.gateway.url` is required.

### Environment variable equivalents

Environment variables remain supported. Common mappings:

| Environment variable | Property key |
|----------|----------|
| `MCP_TRANSPORT` | `mcp.transport` |
| `MCP_HOST` | `mcp.host` |
| `MCP_PORT` | `mcp.port` |
| `NIFI_API_BASE` | `nifi.api.base` |
| `KNOX_TOKEN` | `knox.token` |
| `NIFI_READONLY` | `nifi.readonly` |
| `KNOX_VERIFY_SSL` | `knox.verify.ssl` |
| `KNOX_CA_BUNDLE` | `knox.ca.bundle` |


For the NIFI_API_BASE, form using the url from Knox (less `-token`), and add the postfix `/nifi-app/nifi-api`
So, `https://nifi-2-dh-management0.yourdomain.cloudera.site/nifi-2-dh/cdp-proxy-token` becomes `https://nifi-2-dh-management0.yourdomain.cloudera.site/nifi-2-dh/cdp-proxy/nifi-app/nifi-api`

Get Knox Token from the Flow Management Datahub Knox instance:

![](/screenshots/knox-token-generation.png)


## Example Usage

### Read-Only Operations (Default)

Once configured, you can ask Claude questions like:

- "What version of NiFi am I running?"
- "List all processors in the root process group"
- "Show me recent bulletins"
- "What parameter contexts are configured?"
- "Tell me about the controller services"
- "What processor types are available for building flows?"
- "Search for processors containing 'kafka'"
- "Show me the details of connection abc-123"

### Write Operations (when nifi.readonly=false)

**⚠️ WARNING: Write operations modify your NiFi flows. Use with caution!**

To enable write operations, set `nifi.readonly=false` (or env `NIFI_READONLY=false`) in your configuration. Then you can:

- **Build flows**: "Create a LogAttribute processor named 'MyLogger' in the root process group"
- **Manage processors**: "Start processor with ID abc-123", "Stop all processors in group xyz"
- **Connect components**: "Create a connection from processor A to processor B for the 'success' relationship"
- **Configure**: "Update the scheduling period of processor abc-123 to 30 seconds"
- **Control services**: "Enable the DBCPConnectionPool controller service"

**Examples:**
```
"Create a GenerateFlowFile processor in process group abc-123"
"Connect processor source-123 to processor dest-456 for success relationship"
"Start processor xyz-789"
"Check the queue status for connection conn-456"
"Empty the queue for connection conn-456 before deletion"  (⚠️ deletes flowfiles permanently)
"Delete connection conn-456"
```

**Important Notes:**
- **Version Tracking:** NiFi uses optimistic locking. Always fetch current versions before updates:
  ```python
  processor = get_processor_details(processor_id)
  current_version = processor['revision']['version']
  stop_processor(processor_id, current_version)
  ```
- **Queue Management:** Connections with flowfiles cannot be deleted. Use `get_connection_details()` to check queue status, then `empty_connection_queue()` if needed before deletion.


**Using the example `"List all processors in the root process group"`, we see the following for the example NiFi Canvas:**

![](/screenshots/nifi-canvas-1.png)

![](/screenshots/nifi-readcanvas-1.png)


**Using the example, `"What version of NiFi am I running?"`, we see the following:**

![](/screenshots/nifi-version-check.png)


## License

Apache License 2.0
