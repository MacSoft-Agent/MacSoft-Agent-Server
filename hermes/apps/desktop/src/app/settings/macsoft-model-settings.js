import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Cpu, Loader2, Save } from '@/lib/icons';
import { CONTROL_TEXT } from './constants';
import { ListRow, LoadingState, SectionHeading, SettingsContent } from './primitives';
const EMPTY_SETTINGS = { model: '', provider: '' };
export function shouldUseMacSoftModelSettings(customerRuntime, activeView) {
    return customerRuntime && activeView === 'config:model';
}
export function MacSoftModelSettings() {
    const api = window.hermesDesktop?.serverAutoCount;
    const [settings, setSettings] = useState(EMPTY_SETTINGS);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState(null);
    const [error, setError] = useState(null);
    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            if (!api?.loadModel) {
                if (!cancelled) {
                    setError('Unable to load model settings.');
                    setLoading(false);
                }
                return;
            }
            try {
                const loaded = await api.loadModel();
                if (!cancelled) {
                    setSettings(loaded);
                    setError(null);
                }
            }
            catch {
                if (!cancelled) {
                    setError('Unable to load model settings.');
                }
            }
            finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };
        void load();
        return () => void (cancelled = true);
    }, [api]);
    const save = async () => {
        if (!api?.saveModel || !settings.provider.trim() || !settings.model.trim()) {
            setMessage(null);
            setError('Provider and model are required.');
            return;
        }
        setSaving(true);
        setMessage(null);
        setError(null);
        try {
            const result = await api.saveModel({
                model: settings.model.trim(),
                provider: settings.provider.trim()
            });
            setSettings(result.settings);
            setMessage('Model settings saved.');
        }
        catch {
            setError('Unable to save model settings.');
        }
        finally {
            setSaving(false);
        }
    };
    if (loading) {
        return _jsx(LoadingState, { label: "Loading model settings" });
    }
    return (_jsxs(SettingsContent, { children: [_jsx(SectionHeading, { icon: Cpu, title: "Model Settings" }), _jsx("p", { className: "mb-4 text-xs leading-5 text-(--ui-text-tertiary)", children: "Configure the provider and model used by MacSoft Agent for new requests." }), _jsxs("div", { className: "grid gap-1", children: [_jsx(ListRow, { action: _jsx(Input, { "aria-label": "Provider", autoComplete: "off", className: CONTROL_TEXT, disabled: saving, onChange: event => setSettings(current => ({ ...current, provider: event.target.value })), spellCheck: false, value: settings.provider }), description: "Provider identifier configured for the internal AI Service.", title: "Provider" }), _jsx(ListRow, { action: _jsx(Input, { "aria-label": "Model", autoComplete: "off", className: CONTROL_TEXT, disabled: saving, onChange: event => setSettings(current => ({ ...current, model: event.target.value })), spellCheck: false, value: settings.model }), description: "Model identifier used for new chat requests.", title: "Model" })] }), error ? (_jsx("p", { className: "mt-3 text-xs text-destructive", role: "alert", children: error })) : null, message ? (_jsx("p", { className: "mt-3 text-xs text-emerald-600 dark:text-emerald-400", role: "status", children: message })) : null, _jsx("div", { className: "mt-5 flex justify-end", children: _jsxs(Button, { disabled: saving, onClick: () => void save(), children: [saving ? _jsx(Loader2, { className: "animate-spin" }) : _jsx(Save, {}), "Save"] }) })] }));
}
