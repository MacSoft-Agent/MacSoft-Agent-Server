# MacSoft Agent Product Foundation

## Brand values

- Product: `MacSoft Agent`
- Product version authority: `C:\MacSoft-Agent\product.json` (`0.1.0`)
- Company: `Mac Soft`
- Windows App ID: `com.macsoft.agent`
- Executable: `MacSoft Agent.exe`
- Installer: `MacSoft-Agent-Setup-${version}.${ext}`
- English assistant identity: `MacSoft Agent`
- Chinese assistant identity: `MacSoft 助手`
- Brand blue: `#048FE0`
- Brand orange: `#FC9421`

The home wordmark is text, not a bitmap. `apps/desktop/src/components/macsoft-wordmark.tsx` owns the colored words and `apps/desktop/src/styles.css` owns the Times New Roman font stack. `apps/desktop/src/components/chat/intro.tsx` places the responsive wordmark on the home page. `apps/desktop/src/components/brand-mark.tsx` provides the compact renderer mark used in About and transient overlays.

The package metadata and source icon wiring live in `apps/desktop/package.json`, `apps/desktop/index.html`, and `apps/desktop/electron/main.ts`. Final icon sources belong in:

- `C:\MacSoft-Agent\branding\logo.png`
- `C:\MacSoft-Agent\branding\logo.ico`
- `C:\MacSoft-Agent\branding\logo.icns` (optional on Windows-only releases)

Copy approved assets to `apps/desktop/assets/icon.png`, `apps/desktop/assets/icon.ico`, and `apps/desktop/assets/icon.icns` before building a release. Do not edit generated `dist` or `release` files.

The approved Windows source assets `branding\logo.png` and `branding\logo.ico` are present. An optional macOS `.icns` remains outside this Windows staging batch.

## Server & AutoCount Settings

The Desktop page is implemented by `apps/desktop/src/app/settings/server-autocount-settings.tsx`. It follows the existing Settings navigation and calls a narrow preload bridge. The renderer never reads configuration files or receives an existing API key.

The request path is:

```text
Settings page
  -> preload bridge
  -> Electron main IPC
  -> server-autocount-config service
  -> validated configuration or read-only health check
```

`apps/desktop/electron/macsoft-product.ts` owns the focused Desktop product path contract. `apps/desktop/electron/server-autocount-config.ts` consumes those paths and owns validation, LAN interface ranking, masked configuration reads, timestamped backups, atomic writes, and readable health results.

### Configuration ownership

| UI field | Configuration owner | Field |
| --- | --- | --- |
| MacSoft Server port | `C:\MacSoft-Agent\server\macsoft-server.yaml` | `server.port` |
| AI Service URL | `C:\MacSoft-Agent\server\macsoft-server.yaml` | `hermes.api_base_url` |
| AI Service port | Server YAML and runtime YAML | `hermes.api_base_url` port and `platforms.api_server.extra.port` |
| AutoCount Cloud URL | `C:\MacSoft-Agent\runtime\plugins\macsoft-autocount\config.json` | `baseUrl` |
| AutoCount API Key | AutoCount plugin JSON | `apiKey` |
| AutoCount Connector ID | AutoCount plugin JSON | `connectorId` |
| AutoCount Company ID | AutoCount plugin JSON | `companyId` |

The existing API key is represented in the renderer only as `apiKeyConfigured: true/false`. Leaving the input blank preserves the existing key. A typed replacement remains masked by default, and values beginning with `Bearer ` are rejected before any file is written.

### LAN address and Client URL

The Electron main process reads active IPv4 addresses from the operating system. Loopback (`127.0.0.1`) and link-local (`169.254.x.x`) addresses are not recommended LAN addresses. Physical Ethernet and Wi-Fi addresses rank ahead of VPN and virtual adapters, but every detected non-loopback address remains selectable.

The UI generates the Client URL from the selected address and current Server port:

```text
http://<selected-address>:<server-port>
```

`127.0.0.1` is shown separately as a local-only option. The Client continues to connect only to MacSoft Server; it never uses the internal AI Service URL.

## Port responsibilities

| Port | Responsibility |
| --- | --- |
| `8787` | MacSoft Server, exposed to MacSoft Client devices |
| `8642` | Internal AI Service used by MacSoft Server |
| `5174` | Desktop renderer development server only; never a product setting |

The production flow remains:

```text
Client -> MacSoft Server -> AI Service -> MacSoft AutoCount plugin
       -> AutoCount Cloud -> Local Connector -> AutoCount Accounting
```

AutoCount business commands still run through the agent/plugin path. The Settings connection test is a read-only administrative call that uses the same connector-status endpoint as the plugin and returns a sanitized status model.

## Client execution progress

MacSoft Server provides optional, backward-compatible `activity-v1` SSE progress. The Client still connects only to port 8787, and existing Clients continue receiving the original chat events. See [MacSoft Client Activity Protocol v1](./MACSOFT_CLIENT_ACTIVITY_PROTOCOL_V1.md) for negotiation, ordering, privacy, fallback, and test guidance.

The Server-owned Client Skill API, Skill ownership/isolation model, generic
AutoCount validator, retry policy, controlled Sales Invoice procedure, and
single-run Tool Activity bridge are documented in
[MacSoft Agent Business Control Layer](./MACSOFT_AGENT_BUSINESS_CONTROL.md).

Authenticated session soft deletion, protected live-information boundaries,
the packaged Tool allowlist, migration/rollback behavior, and pre-packaging
verification are documented in
[MacSoft Pre-packaging Hardening](./MACSOFT_PREPACKAGING_HARDENING.md).

## Saving, restart, and rollback

`Save & Apply` validates every field before writing. It creates a timestamped sibling backup for each changed file and writes replacement content to a same-directory temporary file before an atomic rename. If a multi-file commit fails, the service attempts to restore every original file; backups remain available for manual recovery.

- Changing the Server port or AI Service URL requires a MacSoft Server restart.
- Changing the AI Service port requires an AI Service restart and a MacSoft Server restart.
- AutoCount plugin connection fields are loaded for each plugin request and do not require an automatic process restart.
- The page reports restart requirements and now routes Start/Stop/Restart through the local MacSoft Agent Host. The renderer never manages processes directly.

To roll back, stop the affected service, replace the active file with the required `.backup-<timestamp>` sibling, and start the service again. Verify the selected backup before restoring it because backups may contain secrets.

## Connection tests

1. Open **Settings -> Server & AutoCount**.
2. Select the intended LAN interface and confirm the generated Client URL.
3. Use **Test Server** to check the loopback health endpoint on the configured Server port.
4. Expand **Advanced -> AI Service** and test the internal health endpoint.
5. Confirm Cloud URL, Connector ID, and Company ID. Leave API Key blank to use the saved key.
6. Use **Test AutoCount Connection**. A successful status displays Connector, Company, Database, SQL Server, Connector version, update state, and write authorization when the cloud response provides them.

Connection errors are translated into a short title, explanation, next action, and an optional HTTP-only administrator detail. API keys, response payloads, tokens, prompts, and stack traces are never displayed.

Production paths, first-run initialization, bundled Python, Host controls, customer update isolation, and staging evidence are documented in [MacSoft Agent Production Runtime Foundation](./MACSOFT_PRODUCTION_RUNTIME_FOUNDATION.md).
