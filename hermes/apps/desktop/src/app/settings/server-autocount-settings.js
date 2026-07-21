import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AlertCircle, CheckCircle2, Copy, Cpu, Eye, EyeOff, Globe, KeyRound, Loader2, Play, RefreshCw, Save, Square } from '@/lib/icons';
import { cn } from '@/lib/utils';
import { notify } from '@/store/notifications';
import { CONTROL_TEXT } from './constants';
import { ListRow, LoadingState, SectionHeading, SettingsContent } from './primitives';
const EMPTY_FORM = {
    aiServicePort: '8642',
    aiServiceUrl: 'http://127.0.0.1:8642',
    apiKey: '',
    apiKeyConfigured: false,
    cloudUrl: '',
    companyId: '',
    connectorId: '',
    serverPort: '8787'
};
export function macSoftSettingsErrorMessage(error, fallback) {
    if (!(error instanceof Error) || !error.message.trim()) {
        return fallback;
    }
    return (error.message
        .replace(/^Error invoking remote method '[^']+':\s*/i, '')
        .replace(/^Error:\s*/i, '')
        .trim() || fallback);
}
function formFromSettings(settings) {
    return {
        aiServicePort: String(settings.aiService.port),
        aiServiceUrl: settings.aiService.url,
        apiKey: '',
        apiKeyConfigured: settings.autoCount.apiKeyConfigured,
        cloudUrl: settings.autoCount.cloudUrl,
        companyId: settings.autoCount.companyId,
        connectorId: settings.autoCount.connectorId,
        serverPort: String(settings.server.port)
    };
}
function withPort(rawUrl, rawPort) {
    try {
        const url = new URL(rawUrl);
        url.port = rawPort;
        return url.toString().replace(/\/$/, '');
    }
    catch {
        return rawUrl;
    }
}
function StatusPanel({ result }) {
    if (!result) {
        return (_jsx("div", { className: "rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3 text-xs text-(--ui-text-tertiary)", children: "No connection test has been run yet." }));
    }
    return (_jsxs("div", { className: cn('rounded-xl border px-4 py-3', result.ok
            ? 'border-emerald-500/25 bg-emerald-500/5'
            : 'border-destructive/30 bg-destructive/5'), children: [_jsxs("div", { className: "flex items-start gap-2", children: [result.ok ? (_jsx(CheckCircle2, { className: "mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" })) : (_jsx(AlertCircle, { className: "mt-0.5 size-4 shrink-0 text-destructive" })), _jsxs("div", { className: "min-w-0", children: [_jsx("p", { className: "text-sm font-medium text-foreground", children: result.title }), _jsx("p", { className: "mt-1 text-xs leading-5 text-(--ui-text-tertiary)", children: result.summary }), result.action ? _jsxs("p", { className: "mt-2 text-xs leading-5 text-foreground", children: ["Next: ", result.action] }) : null] })] }), result.fields?.length ? (_jsx("dl", { className: "mt-3 grid gap-x-5 gap-y-2 border-t border-(--ui-stroke-tertiary) pt-3 text-xs sm:grid-cols-2", children: result.fields.map(field => (_jsxs("div", { className: "min-w-0", children: [_jsx("dt", { className: "text-(--ui-text-tertiary)", children: field.label }), _jsx("dd", { className: "mt-0.5 break-words font-medium text-foreground", children: field.value })] }, field.label))) })) : null, result.details ? (_jsxs("details", { className: "mt-3 border-t border-(--ui-stroke-tertiary) pt-2 text-xs text-(--ui-text-tertiary)", children: [_jsx("summary", { className: "cursor-pointer select-none", children: "Administrator detail" }), _jsx("p", { className: "mt-2 font-mono", children: result.details })] })) : null] }));
}
function networkLabel(network) {
    const kind = {
        ethernet: 'Ethernet',
        other: 'Network',
        vpn: 'VPN',
        virtual: 'Virtual',
        wifi: 'Wi-Fi'
    }[network.kind];
    return `${network.interfaceName} · ${kind} · ${network.address}${network.recommended ? ' · Recommended' : ''}`;
}
function ServiceControl({ busy, label, onAction, service }) {
    const status = service?.status || 'stopped';
    const tone = status === 'running' ? 'text-emerald-600 dark:text-emerald-400' : status === 'error' ? 'text-destructive' : 'text-(--ui-text-tertiary)';
    return (_jsx("div", { className: "rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3", children: _jsxs("div", { className: "flex flex-wrap items-center justify-between gap-3", children: [_jsxs("div", { children: [_jsx("p", { className: "text-sm font-medium text-foreground", children: label }), _jsx("p", { className: cn('mt-1 text-xs capitalize', tone), children: status.replace('_', ' ') }), service?.last_error ? _jsx("p", { className: "mt-1 max-w-xl text-xs text-destructive", children: service.last_error }) : null] }), _jsxs("div", { className: "flex flex-wrap gap-2", children: [_jsxs(Button, { disabled: busy || status === 'running' || status === 'starting', onClick: () => onAction('start'), size: "sm", variant: "outline", children: [_jsx(Play, {}), " Start"] }), _jsxs(Button, { disabled: busy || status === 'stopped', onClick: () => onAction('stop'), size: "sm", variant: "outline", children: [_jsx(Square, {}), " Stop"] }), _jsxs(Button, { disabled: busy || status === 'stopped', onClick: () => onAction('restart'), size: "sm", variant: "outline", children: [_jsx(RefreshCw, {}), " Restart"] })] })] }) }));
}
export function ServerAutoCountSettingsPage() {
    const api = window.hermesDesktop?.serverAutoCount;
    const hostApi = window.hermesDesktop?.macSoftHost;
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(null);
    const [showApiKey, setShowApiKey] = useState(false);
    const [settings, setSettings] = useState(null);
    const [form, setForm] = useState(EMPTY_FORM);
    const [selectedAddress, setSelectedAddress] = useState('');
    const [serverStatus, setServerStatus] = useState(null);
    const [aiStatus, setAiStatus] = useState(null);
    const [autoCountStatus, setAutoCountStatus] = useState(null);
    const [loadError, setLoadError] = useState(null);
    const [hostStatus, setHostStatus] = useState(null);
    const [hostError, setHostError] = useState(null);
    const [serviceAction, setServiceAction] = useState(null);
    const [pairingCode, setPairingCode] = useState(null);
    const [pairingError, setPairingError] = useState(null);
    const [gettingPairingCode, setGettingPairingCode] = useState(false);
    const applyLoadedSettings = (next) => {
        setSettings(next);
        setForm(formFromSettings(next));
        setServerStatus(next.server.status);
        setAiStatus(next.aiService.status);
        setSelectedAddress(current => {
            if (next.networkAddresses.some(network => network.address === current) || current === next.localOnlyAddress) {
                return current;
            }
            return next.recommendedAddress || next.localOnlyAddress;
        });
    };
    const load = async () => {
        if (!api) {
            setLoadError('The Desktop configuration bridge is unavailable.');
            setLoading(false);
            return;
        }
        setLoading(true);
        setLoadError(null);
        try {
            applyLoadedSettings(await api.load());
        }
        catch (error) {
            setLoadError(macSoftSettingsErrorMessage(error, 'Could not load Server & AutoCount settings.'));
        }
        finally {
            setLoading(false);
        }
    };
    const refreshHostStatus = async () => {
        if (!hostApi) {
            setHostError('The Desktop Host bridge is unavailable.');
            return;
        }
        try {
            setHostStatus(await hostApi.status());
            setHostError(null);
        }
        catch (error) {
            setHostError(macSoftSettingsErrorMessage(error, 'MacSoft Agent Host is unavailable.'));
        }
    };
    const runServiceAction = async (name, action) => {
        if (!hostApi)
            return;
        setServiceAction(name);
        try {
            await hostApi.serviceAction(name, action);
            await refreshHostStatus();
        }
        catch (error) {
            setHostError(macSoftSettingsErrorMessage(error, 'The service action failed.'));
        }
        finally {
            setServiceAction(null);
        }
    };
    const setAutoStart = async (enabled) => {
        if (!hostApi)
            return;
        try {
            const autoStart = await hostApi.setAutoStart(enabled);
            setHostStatus(current => (current ? { ...current, auto_start: autoStart } : current));
        }
        catch (error) {
            setHostError(macSoftSettingsErrorMessage(error, 'Auto-start could not be updated.'));
        }
    };
    useEffect(() => {
        void load();
        void refreshHostStatus();
        // eslint-disable-next-line react-hooks/exhaustive-deps -- load once when the page opens
    }, []);
    const clientUrl = useMemo(() => `http://${selectedAddress || settings?.recommendedAddress || settings?.localOnlyAddress || '127.0.0.1'}:${form.serverPort || '8787'}`, [form.serverPort, selectedAddress, settings?.localOnlyAddress, settings?.recommendedAddress]);
    const savePayload = () => ({
        aiServicePort: Number(form.aiServicePort),
        aiServiceUrl: form.aiServiceUrl,
        apiKey: form.apiKey.trim() || undefined,
        cloudUrl: form.cloudUrl,
        companyId: form.companyId,
        connectorId: form.connectorId,
        serverPort: Number(form.serverPort)
    });
    const autoCountPayload = () => ({
        apiKey: form.apiKey.trim() || undefined,
        cloudUrl: form.cloudUrl,
        companyId: form.companyId,
        connectorId: form.connectorId
    });
    const refreshNetworks = async () => {
        if (!api) {
            return;
        }
        try {
            const network = await api.refreshNetworks();
            setSettings(current => current
                ? { ...current, networkAddresses: network.addresses, recommendedAddress: network.recommendedAddress }
                : current);
            setSelectedAddress(network.recommendedAddress || '127.0.0.1');
        }
        catch (error) {
            notify({
                kind: 'error',
                message: macSoftSettingsErrorMessage(error, 'Network interfaces could not be refreshed.'),
                title: 'Refresh failed'
            });
        }
    };
    const copyClientUrl = async () => {
        try {
            await window.hermesDesktop.writeClipboard(clientUrl);
            notify({ kind: 'success', message: clientUrl, title: 'Client URL copied' });
        }
        catch {
            notify({ kind: 'error', message: 'Copy the URL manually from the field.', title: 'Copy failed' });
        }
    };
    const getPairingCode = async () => {
        if (!api)
            return;
        setGettingPairingCode(true);
        setPairingCode(null);
        setPairingError(null);
        try {
            setPairingCode(await api.getPairingCode(Number(form.serverPort)));
        }
        catch {
            setPairingError('Unable to get pairing code.');
        }
        finally {
            setGettingPairingCode(false);
        }
    };
    const testServer = async () => {
        if (!api) {
            return;
        }
        setTesting('server');
        try {
            setServerStatus(await api.testServer(Number(form.serverPort)));
        }
        finally {
            setTesting(null);
        }
    };
    const testAiService = async () => {
        if (!api) {
            return;
        }
        setTesting('ai');
        try {
            setAiStatus(await api.testAiService(withPort(form.aiServiceUrl, form.aiServicePort)));
        }
        finally {
            setTesting(null);
        }
    };
    const testAutoCount = async () => {
        if (!api) {
            return;
        }
        setTesting('autocount');
        try {
            setAutoCountStatus(await api.testAutoCount(autoCountPayload()));
        }
        catch (error) {
            setAutoCountStatus({
                action: 'Review the fields and try again.',
                ok: false,
                summary: macSoftSettingsErrorMessage(error, 'The connection test could not be completed.'),
                title: 'AutoCount test failed'
            });
        }
        finally {
            setTesting(null);
        }
    };
    const save = async () => {
        if (!api) {
            return;
        }
        setSaving(true);
        try {
            const result = await api.save(savePayload());
            applyLoadedSettings(result.settings);
            setAutoCountStatus(null);
            notify({
                kind: 'success',
                message: result.restartRequired
                    ? `Saved safely. Restart required: ${result.servicesToRestart.join(', ')}.`
                    : 'Saved safely. No service restart is required.',
                title: 'Server & AutoCount settings saved'
            });
        }
        catch (error) {
            notify({
                kind: 'error',
                message: macSoftSettingsErrorMessage(error, 'The settings could not be saved.'),
                title: 'Save failed'
            });
        }
        finally {
            setSaving(false);
        }
    };
    if (loading) {
        return _jsx(LoadingState, { label: "Loading Server & AutoCount settings..." });
    }
    if (loadError || !settings) {
        return (_jsx(SettingsContent, { children: _jsxs("div", { className: "rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3", children: [_jsx("p", { className: "text-sm font-medium text-destructive", children: "Settings could not be loaded" }), _jsx("p", { className: "mt-1 text-xs leading-5 text-(--ui-text-tertiary)", children: loadError }), _jsxs(Button, { className: "mt-3", onClick: () => void load(), size: "sm", variant: "outline", children: [_jsx(RefreshCw, {}), " Retry"] })] }) }));
    }
    return (_jsxs(SettingsContent, { children: [_jsxs("div", { className: "mb-6", children: [_jsx("h2", { className: "text-lg font-semibold tracking-tight", children: "Server & AutoCount" }), _jsx("p", { className: "mt-1 max-w-2xl text-xs leading-5 text-(--ui-text-tertiary)", children: "Configure the Client-facing MacSoft Server, internal AI Service, and AutoCount Cloud connection. Saving never starts or stops a service automatically." })] }), _jsx(SectionHeading, { icon: Cpu, title: "Service Control" }), _jsxs("div", { className: "grid gap-3", children: [_jsx(ServiceControl, { busy: serviceAction === 'ai_service', label: "AI Service", onAction: action => void runServiceAction('ai_service', action), service: hostStatus?.services.ai_service }), _jsx(ServiceControl, { busy: serviceAction === 'server', label: "MacSoft Server", onAction: action => void runServiceAction('server', action), service: hostStatus?.services.server })] }), _jsxs("div", { className: "mt-3 flex flex-wrap items-center gap-4", children: [_jsxs(Button, { onClick: () => void refreshHostStatus(), size: "sm", variant: "textStrong", children: [_jsx(RefreshCw, {}), " Refresh Status"] }), _jsxs("label", { className: "flex items-center gap-2 text-xs text-foreground", children: [_jsx("input", { checked: hostStatus?.auto_start ?? true, disabled: !hostStatus, onChange: event => void setAutoStart(event.target.checked), type: "checkbox" }), "Auto-start services with Windows"] })] }), hostError ? _jsx("p", { className: "mt-3 text-xs text-destructive", children: hostError }) : null, _jsxs("details", { className: "mt-3 rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3 text-xs text-(--ui-text-tertiary)", children: [_jsx("summary", { className: "cursor-pointer select-none", children: "Administrator details" }), _jsxs("dl", { className: "mt-3 grid gap-2 sm:grid-cols-2", children: [_jsxs("div", { children: [_jsx("dt", { children: "Host version" }), _jsx("dd", { className: "font-mono text-foreground", children: hostStatus?.version || 'Unavailable' })] }), _jsxs("div", { children: [_jsx("dt", { children: "AI Service PID" }), _jsx("dd", { className: "font-mono text-foreground", children: hostStatus?.services.ai_service.pid || 'Not running' })] }), _jsxs("div", { children: [_jsx("dt", { children: "Server PID" }), _jsx("dd", { className: "font-mono text-foreground", children: hostStatus?.services.server.pid || 'Not running' })] }), _jsxs("div", { children: [_jsx("dt", { children: "Control boundary" }), _jsx("dd", { className: "text-foreground", children: "Local Host interface only" })] })] })] }), settings.warnings.map(warning => (_jsxs("div", { className: "mb-4 flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2.5 text-xs", children: [_jsx(AlertCircle, { className: "mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" }), _jsx("span", { children: warning })] }, warning))), _jsx(SectionHeading, { icon: Globe, title: "MacSoft Server" }), _jsxs("div", { className: "grid gap-1", children: [_jsx(ListRow, { action: _jsx(Input, { "aria-label": "Server port", className: cn('h-8 w-36', CONTROL_TEXT), max: 65535, min: 1, onChange: event => setForm(current => ({ ...current, serverPort: event.target.value })), type: "number", value: form.serverPort }), description: "Client-facing port. MacSoft Client connects here, not to the AI Service.", title: "Server port" }), _jsx(ListRow, { action: _jsxs("select", { "aria-label": "Selected network interface", className: "h-8 min-w-64 max-w-full rounded-md border border-input bg-transparent px-2 text-xs text-foreground", onChange: event => setSelectedAddress(event.target.value), value: selectedAddress, children: [settings.networkAddresses.map(network => (_jsx("option", { value: network.address, children: networkLabel(network) }, network.id))), _jsx("option", { value: settings.localOnlyAddress, children: "This computer only \u00B7 127.0.0.1" })] }), description: "Physical Wi-Fi or Ethernet is recommended. Virtual and VPN addresses remain selectable.", title: "Network interface" }), _jsx(ListRow, { action: _jsxs("div", { className: "flex max-w-full items-center gap-2", children: [_jsx(Input, { "aria-label": "Client URL", className: "h-8 min-w-0 font-mono text-xs", readOnly: true, value: clientUrl }), _jsx(Button, { "aria-label": "Copy Client URL", onClick: () => void copyClientUrl(), size: "icon-sm", variant: "outline", children: _jsx(Copy, {}) })] }), description: selectedAddress === settings.localOnlyAddress
                            ? 'Local-only URL. Other computers cannot use this address.'
                            : 'Share this URL with MacSoft Client devices on the same local network.', title: "Client URL" }), _jsx(ListRow, { action: _jsxs("div", { className: "flex items-center gap-3", children: [_jsxs(Button, { disabled: hostStatus?.services.server.status !== 'running' || gettingPairingCode, onClick: () => void getPairingCode(), size: "sm", variant: "outline", children: [gettingPairingCode ? _jsx(Loader2, { className: "animate-spin" }) : null, "Get Code"] }), pairingCode ? _jsx("span", { className: "font-mono text-sm font-semibold text-foreground", children: pairingCode }) : null] }), description: hostStatus?.services.server.status !== 'running'
                            ? 'MacSoft Server is not running.'
                            : pairingError || 'Request a one-time code for pairing a MacSoft Client.', title: "Pairing Code" })] }), _jsxs("div", { className: "mt-3 flex flex-wrap gap-4", children: [_jsxs(Button, { onClick: () => void refreshNetworks(), size: "sm", variant: "textStrong", children: [_jsx(RefreshCw, {}), " Refresh IP"] }), _jsxs(Button, { disabled: testing === 'server', onClick: () => void testServer(), size: "sm", variant: "outline", children: [testing === 'server' ? _jsx(Loader2, { className: "animate-spin" }) : null, "Test Server"] })] }), _jsx("div", { className: "mt-4", children: _jsx(StatusPanel, { result: serverStatus }) }), _jsxs("details", { className: "mt-8 rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3", children: [_jsx("summary", { className: "cursor-pointer select-none text-sm font-medium", children: "Advanced \u00B7 AI Service" }), _jsxs("div", { className: "mt-4", children: [_jsx(SectionHeading, { icon: Cpu, title: "AI Service" }), _jsxs("div", { className: "grid gap-1", children: [_jsx(ListRow, { action: _jsx(Input, { "aria-label": "AI Service URL", className: cn('h-8 font-mono', CONTROL_TEXT), onChange: event => setForm(current => ({ ...current, aiServiceUrl: event.target.value })), value: form.aiServiceUrl }), description: "Internal service used by MacSoft Server. It is not a Client URL.", title: "Service URL" }), _jsx(ListRow, { action: _jsx(Input, { "aria-label": "AI Service port", className: cn('h-8 w-36', CONTROL_TEXT), max: 65535, min: 1, onChange: event => setForm(current => ({ ...current, aiServicePort: event.target.value })), type: "number", value: form.aiServicePort }), description: "Changing this updates the runtime API Server port and MacSoft Server URL together.", title: "Service port" })] }), _jsxs(Button, { className: "mt-3", disabled: testing === 'ai', onClick: () => void testAiService(), size: "sm", variant: "outline", children: [testing === 'ai' ? _jsx(Loader2, { className: "animate-spin" }) : null, "Test AI Service"] }), _jsx("div", { className: "mt-4", children: _jsx(StatusPanel, { result: aiStatus }) })] })] }), _jsxs("div", { className: "mt-8", children: [_jsx(SectionHeading, { icon: KeyRound, title: "AutoCount Connection" }), _jsxs("div", { className: "grid gap-1", children: [_jsx(ListRow, { action: _jsx(Input, { className: cn('h-8 font-mono', CONTROL_TEXT), onChange: event => setForm(current => ({ ...current, cloudUrl: event.target.value })), value: form.cloudUrl }), description: "AutoCount Cloud API base URL.", title: "Cloud URL" }), _jsx(ListRow, { action: _jsxs("div", { className: "flex items-center gap-2", children: [_jsx(Input, { autoComplete: "off", className: cn('h-8 font-mono', CONTROL_TEXT), onChange: event => setForm(current => ({ ...current, apiKey: event.target.value })), placeholder: form.apiKeyConfigured ? 'Existing key configured · leave blank to keep' : 'Enter API Key', type: showApiKey ? 'text' : 'password', value: form.apiKey }), _jsx(Button, { "aria-label": showApiKey ? 'Hide API Key' : 'Reveal typed API Key', onClick: () => setShowApiKey(value => !value), size: "icon-sm", type: "button", variant: "outline", children: showApiKey ? _jsx(EyeOff, {}) : _jsx(Eye, {}) })] }), description: "The existing key is never loaded into this page. Leave blank to preserve it; do not include a Bearer prefix.", title: "API Key" }), _jsx(ListRow, { action: _jsx(Input, { className: cn('h-8 font-mono', CONTROL_TEXT), onChange: event => setForm(current => ({ ...current, connectorId: event.target.value })), value: form.connectorId }), description: "Selects the registered Local Connector.", title: "Connector ID" }), _jsx(ListRow, { action: _jsx(Input, { className: cn('h-8 font-mono', CONTROL_TEXT), onChange: event => setForm(current => ({ ...current, companyId: event.target.value })), value: form.companyId }), description: "Selects the company/account book exposed by the Connector. Database details are read-only test results.", title: "Company ID" })] }), _jsxs(Button, { className: "mt-3", disabled: testing === 'autocount', onClick: () => void testAutoCount(), size: "sm", variant: "outline", children: [testing === 'autocount' ? _jsx(Loader2, { className: "animate-spin" }) : null, "Test AutoCount Connection"] }), _jsx("div", { className: "mt-4", children: _jsx(StatusPanel, { result: autoCountStatus }) })] }), _jsxs("div", { className: "mt-8 flex flex-wrap items-center justify-end gap-3 border-t border-(--ui-stroke-tertiary) pt-5", children: [_jsx("p", { className: "mr-auto max-w-xl text-xs leading-5 text-(--ui-text-tertiary)", children: "Save creates timestamped backups and atomically replaces validated configuration files. The result will list any required service restarts." }), _jsxs(Button, { disabled: saving, onClick: () => void save(), size: "sm", children: [saving ? _jsx(Loader2, { className: "animate-spin" }) : _jsx(Save, {}), "Save & Apply"] })] })] }));
}
