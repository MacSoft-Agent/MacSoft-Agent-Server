import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useStore } from '@nanostores/react';
import { useEffect } from 'react';
import { BrandMark } from '@/components/brand-mark';
import { RefreshCw } from '@/lib/icons';
import { $desktopVersion, refreshDesktopVersion } from '@/store/updates';
import { SectionHeading, SettingsContent } from './primitives';
export function AboutSettings() {
    const version = useStore($desktopVersion);
    useEffect(() => {
        void refreshDesktopVersion();
    }, []);
    return (_jsxs(SettingsContent, { children: [_jsxs("div", { className: "flex flex-col items-center gap-3 pt-6 pb-2 text-center", children: [_jsx(BrandMark, { className: "size-16" }), _jsxs("div", { children: [_jsx("h2", { className: "text-lg font-semibold tracking-tight", children: "MacSoft Agent" }), _jsx("p", { className: "mt-1 text-xs text-muted-foreground", children: version?.appVersion ? `Version ${version.appVersion}` : 'Version unavailable' })] })] }), _jsxs("div", { className: "mx-auto mt-4 w-full max-w-2xl", children: [_jsx(SectionHeading, { icon: RefreshCw, title: "Updates" }), _jsxs("div", { className: "rounded-xl border border-border/70 bg-muted/20 px-4 py-3 text-sm text-foreground", children: [_jsx("p", { className: "font-medium", children: "Updates are installed using a MacSoft Agent installer." }), _jsx("p", { className: "mt-1 text-xs text-muted-foreground", children: "This build does not contact or modify a source repository." })] })] })] }));
}
