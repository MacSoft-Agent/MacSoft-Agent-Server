from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "packaging" / "installer" / "MacSoft-Agent.nsi"
MAINTENANCE_SCRIPT = ROOT / "packaging" / "installer" / "maintenance.ps1"
STAGING_MANIFEST = (
    ROOT
    / "staging"
    / "MacSoft-Agent-0.1.0-20260714.9"
    / "staging-manifest.json"
)


class PackagingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.installer = INSTALLER.read_text(encoding="utf-8-sig")
        cls.maintenance = MAINTENANCE_SCRIPT.read_text(encoding="utf-8-sig")
        cls.install_section = cls.installer.split(
            'Section "Install MacSoft Agent" SEC_MAIN', 1
        )[1].split("SectionEnd", 1)[0]

    def test_normal_uninstall_preserves_programdata_and_purge_is_explicit(self) -> None:
        self.assertIn("StrCpy $PurgeData 0", self.installer)
        self.assertIn('"/PURGEDATA"', self.installer)
        self.assertIn("${NSD_Uncheck} $PurgeCheckbox", self.installer)
        self.assertIn(
            "Remove all MacSoft Agent data, credentials, sessions, settings, and logs",
            self.installer,
        )
        self.assertIn("This action cannot be undone", self.installer)
        self.assertIn("if ($PurgeData -ne 1", self.maintenance)
        self.assertNotIn('RMDir /r "$APPDATA\\MacSoft Agent"', self.installer)

    def test_uninstall_is_checked_and_has_reboot_fallback(self) -> None:
        self.assertIn("Stop-OwnedServiceTree", self.maintenance)
        self.assertIn("Get-DescendantProcessIds", self.maintenance)
        self.assertIn("$service.State -ne 'Stopped'", self.maintenance)
        self.assertIn("@(0, 1060, 1072)", self.maintenance)
        self.assertIn("MoveFileEx", self.maintenance)
        self.assertIn("exit 3010", self.maintenance)
        self.assertIn("Remove-NetFirewallRule", self.maintenance)
        self.assertIn("Delete /REBOOTOK", self.installer)
        self.assertIn("RMDir /r /REBOOTOK", self.installer)
        self.assertIn("cleanup could not be completed or safely scheduled", self.installer)

    def test_preinstall_cleanup_precedes_program_payload_extraction(self) -> None:
        cleanup_index = self.install_section.index("-Action PreInstall")
        set_out_path_index = self.install_section.index('SetOutPath "$INSTDIR"')
        payload_index = self.install_section.index('File /r "${PAYLOAD_ROOT}\\*.*"')
        self.assertLess(cleanup_index, set_out_path_index)
        self.assertLess(cleanup_index, payload_index)
        self.assertIn("[ValidateSet('PreInstall', 'Cleanup')]", self.maintenance)
        self.assertIn("$servicePresent = $null -ne (Get-ServiceRecord)", self.maintenance)
        self.assertIn(
            "Test-Path -LiteralPath $ProgramRoot -PathType Container",
            self.maintenance,
        )

    def test_upgrade_process_cleanup_is_install_root_scoped(self) -> None:
        self.assertIn("Get-InstalledProgramProcesses", self.maintenance)
        self.assertIn("[string]$process.ExecutablePath", self.maintenance)
        self.assertIn(
            "StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)",
            self.maintenance,
        )
        self.assertIn("$normalizedRoot + [IO.Path]::DirectorySeparatorChar", self.maintenance)
        self.assertIn("CloseMainWindow()", self.maintenance)
        self.assertIn("Stop-Process -Id $remainingProcessId -Force", self.maintenance)
        self.assertIn("MacSoft Agent processes remain active under $ProgramRoot", self.maintenance)
        self.assertNotIn("Get-Process -Name", self.maintenance)
        for generic_name in ("python.exe", "node.exe", "electron.exe", "chrome.exe"):
            self.assertNotIn(generic_name, self.maintenance.lower())

    def test_preinstall_never_deletes_programdata_or_program_files(self) -> None:
        preinstall_block = self.maintenance.split(
            "if ($Action -eq 'PreInstall')", 1
        )[1].split("if ($Action -eq 'Cleanup')", 1)[0]
        self.assertNotIn("Remove-Item", preinstall_block)
        self.assertNotIn("Remove-DataIfRequested", preinstall_block)
        self.assertNotIn("Remove-ServiceChecked", preinstall_block)
        self.assertNotIn("Remove-FirewallRuleChecked", preinstall_block)
        self.assertNotIn("RMDir", self.install_section)
        self.assertNotIn('RMDir /r "$APPDATA\\MacSoft Agent"', self.installer)

    def test_packaged_payload_does_not_contain_a_database(self) -> None:
        manifest = json.loads(STAGING_MANIFEST.read_text(encoding="utf-8"))
        packaged_databases = [
            entry["path"]
            for entry in manifest["files"]
            if entry["path"].lower().endswith(".db")
            or entry["path"].lower().endswith("macsoft-server.db")
        ]
        self.assertEqual(packaged_databases, [])

    def test_maintenance_has_no_pid_automatic_variable_collision(self) -> None:
        self.assertIsNone(re.search(r"\$pid\b", self.maintenance, re.IGNORECASE))
        self.assertIn("$childProcessId = [int]$process.ProcessId", self.maintenance)

    def test_programdata_uses_pre_b06_working_permissions(self) -> None:
        self.assertNotIn("configure-data-acl.ps1", self.installer)
        self.assertNotIn("/inheritance:r", self.installer)
        self.assertIn('CreateDirectory "$APPDATA\\MacSoft Agent"', self.installer)
        self.assertIn(
            '"$SYSDIR\\icacls.exe" "$APPDATA\\MacSoft Agent" /inheritance:e',
            self.installer,
        )
        self.assertIn('"*S-1-5-18:(OI)(CI)F"', self.installer)
        self.assertIn('"*S-1-5-32-544:(OI)(CI)F"', self.installer)
        self.assertIn('"*S-1-5-19:(OI)(CI)M"', self.installer)
        self.assertIn('"*S-1-5-32-545:(OI)(CI)M"', self.installer)

    def test_no_everyone_or_users_full_control_workaround(self) -> None:
        self.assertNotIn("S-1-1-0:(OI)(CI)F", self.installer)
        self.assertNotIn("S-1-5-32-545:(OI)(CI)F", self.installer)

    def test_custom_acl_hardening_helper_was_removed(self) -> None:
        self.assertFalse(
            (ROOT / "packaging" / "installer" / "configure-data-acl.ps1").exists()
        )

    def test_host_service_registration_remains_present(self) -> None:
        self.assertIn(
            '-m macsoft_runtime.service --username "NT AUTHORITY\\LocalService" '
            "--startup auto install",
            self.installer,
        )
        self.assertIn(
            '-m macsoft_runtime.service --username "NT AUTHORITY\\LocalService" '
            "--startup auto update",
            self.installer,
        )
        self.assertIn('"$SYSDIR\\sc.exe" query ${SERVICE_NAME}', self.installer)
        self.assertIn('"$SYSDIR\\sc.exe" start ${SERVICE_NAME}', self.installer)
        self.assertIn("sidtype ${SERVICE_NAME} unrestricted", self.installer)

    def test_desktop_shortcut_uses_server_name_and_cleans_legacy_name(self) -> None:
        self.assertIn('!define DESKTOP_SHORTCUT_NAME "MacSoft Server"', self.installer)
        self.assertIn(
            'CreateShortcut "$DESKTOP\\${DESKTOP_SHORTCUT_NAME}.lnk"',
            self.installer,
        )
        self.assertNotIn('CreateShortcut "$DESKTOP\\MacSoft Agent.lnk"', self.installer)
        self.assertIn('Delete "$DESKTOP\\MacSoft Agent.lnk"', self.installer)
        self.assertGreaterEqual(
            self.installer.count(
                'Delete "$DESKTOP\\${DESKTOP_SHORTCUT_NAME}.lnk"'
            ),
            2,
        )

    def test_source_directory_is_never_an_uninstall_target(self) -> None:
        combined = self.installer + self.maintenance
        self.assertNotIn("C:\\MacSoft-Agent", combined)
        self.assertIn('ProgramRoot "$INSTDIR"', self.installer)
        self.assertIn('DataRoot "$APPDATA\\MacSoft Agent"', self.installer)


if __name__ == "__main__":
    unittest.main()
