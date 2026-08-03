from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "packaging" / "installer" / "MacSoft-Agent.nsi"
MAINTENANCE_SCRIPT = ROOT / "packaging" / "installer" / "maintenance.ps1"
VERIFY_HEALTH_SCRIPT = ROOT / "packaging" / "installer" / "verify-health.ps1"
STAGING_SOURCE = ROOT / "product_runtime" / "macsoft_runtime" / "staging.py"


class PackagingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.installer = INSTALLER.read_text(encoding="utf-8-sig")
        cls.maintenance = MAINTENANCE_SCRIPT.read_text(encoding="utf-8-sig")
        cls.verify_health = VERIFY_HEALTH_SCRIPT.read_text(encoding="utf-8-sig")
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

    def test_server_runtime_dependencies_use_the_unified_product_uv_lock(self) -> None:
        pyproject = tomllib.loads((ROOT / "hermes" / "pyproject.toml").read_text(encoding="utf-8"))
        server_project = tomllib.loads((ROOT / "server" / "pyproject.toml").read_text(encoding="utf-8"))
        requirements = {
            line.strip().replace('"', "'")
            for line in (ROOT / "server" / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        product_extra = {
            dependency.replace('"', "'")
            for dependency in pyproject["project"]["optional-dependencies"]["macsoft-server"]
        }
        sync_script = (ROOT / "scripts" / "sync-server-runtime-dependencies.ps1").read_text(encoding="utf-8-sig")
        self.assertEqual(requirements, product_extra)
        self.assertEqual(requirements, {dependency.replace('"', "'") for dependency in server_project["project"]["dependencies"]})
        self.assertIn("hermes-agent[macsoft-server]", pyproject["project"]["optional-dependencies"]["all"])
        self.assertTrue((ROOT / "hermes" / "uv.lock").is_file())
        self.assertTrue((ROOT / "server" / "uv.lock").is_file())
        self.assertIn("'--extra', 'all'", sync_script)
        self.assertIn("'--locked'", sync_script)

        product_lock = tomllib.loads((ROOT / "hermes" / "uv.lock").read_text(encoding="utf-8"))
        server_lock = tomllib.loads((ROOT / "server" / "uv.lock").read_text(encoding="utf-8"))
        product_versions = {item["name"]: item["version"] for item in product_lock["package"] if "version" in item}
        server_versions = {item["name"]: item["version"] for item in server_lock["package"] if "version" in item}
        overlap = product_versions.keys() & server_versions.keys()
        self.assertGreater(len(overlap), 10)
        self.assertEqual(
            {name: server_versions[name] for name in overlap},
            {name: product_versions[name] for name in overlap},
        )

    def test_product_runtime_installs_locked_hermes_voice_extra(self) -> None:
        pyproject = tomllib.loads((ROOT / "hermes" / "pyproject.toml").read_text(encoding="utf-8"))
        product_lock = tomllib.loads((ROOT / "hermes" / "uv.lock").read_text(encoding="utf-8"))
        voice_dependencies = pyproject["project"]["optional-dependencies"]["voice"]
        locked_names = {item["name"] for item in product_lock["package"]}
        sync_script = (ROOT / "scripts" / "sync-server-runtime-dependencies.ps1").read_text(encoding="utf-8-sig")
        release_script = (ROOT / "scripts" / "build-release.ps1").read_text(encoding="utf-8-sig")

        self.assertTrue(any(dependency.startswith("faster-whisper==") for dependency in voice_dependencies))
        self.assertIn("faster-whisper", locked_names)
        self.assertIn("'--extra', 'voice'", sync_script)
        self.assertIn("import fastapi, faster_whisper", sync_script)
        self.assertIn("--extra all --extra voice --locked", release_script)

    def test_source_test_runtime_owns_the_complete_host_and_desktop_lifecycle(self) -> None:
        start = (ROOT / "scripts" / "start-test-runtime.ps1").read_text(encoding="utf-8-sig")
        stop = (ROOT / "scripts" / "stop-test-runtime.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("product_runtime.macsoft_runtime.cli", start)
        self.assertIn("'development'", start)
        self.assertIn("dev:macsoft", start)
        self.assertIn("desktop_pid", start)
        self.assertIn("test-runtime.json", start)
        self.assertIn("Stop-RecordedProcessTree", stop)
        self.assertIn("dev:macsoft", stop)
        self.assertIn("product_runtime.macsoft_runtime.cli", stop)
        self.assertIn("@(8766, 8643, 8642, 8787, 5174)", stop)

    def test_mutable_development_state_is_ignored_but_templates_remain(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("runtime/", ignore)
        self.assertIn("server/data/", ignore)
        self.assertIn("server/initialization.json", ignore)
        self.assertTrue((ROOT / "runtime.example" / "config.yaml.example").is_file())
        self.assertTrue((ROOT / "packaging" / "templates" / "runtime" / "config.yaml").is_file())

    def test_autocount_skill_requires_renderer_safe_business_lists(self) -> None:
        plugin_root = (
            ROOT
            / "packaging"
            / "templates"
            / "protected"
            / "runtime"
            / "plugins"
            / "macsoft-autocount"
        )
        policy = (plugin_root / "__init__.py").read_text(encoding="utf-8")
        skill = (
            plugin_root / "skills" / "autocount-operations" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for content in (policy, skill):
            normalized = " ".join(content.split())
            self.assertIn("Markdown table or bullet list", normalized)
            self.assertIn("bare newline-separated", normalized)
            self.assertIn("customer-readable business labels", normalized)

        product = json.loads((ROOT / "product.json").read_text(encoding="utf-8"))
        protected = json.loads(
            (ROOT / "packaging" / "templates" / "protected-resources.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            product["protected_resource_version"], protected["version"]
        )

    def test_release_build_is_clean_commit_gated_and_version_driven(self) -> None:
        release = (ROOT / "scripts" / "build-release.ps1").read_text(encoding="utf-8-sig")
        finalizer = (ROOT / "scripts" / "finalize-release-artifact.ps1").read_text(encoding="utf-8-sig")
        rfc3161_verifier = (ROOT / "scripts" / "verify-rfc3161-timestamp.ps1").read_text(encoding="utf-8-sig")
        staging = (ROOT / "scripts" / "build-staging.ps1").read_text(encoding="utf-8-sig")
        installer_builder = (ROOT / "packaging" / "build-installer.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("MacSoft-Agent-Packaging", release)
        self.assertIn("status --porcelain", release)
        self.assertIn("$ExpectedCommit", release)
        self.assertIn("--extra all --extra voice --locked", release)
        self.assertIn("ci", release)
        self.assertIn("run pack --workspace apps/desktop", release)
        self.assertIn("build-staging.ps1", release)
        self.assertIn("build-installer.ps1", release)
        self.assertIn("finalize-release-artifact.ps1", release)
        self.assertIn("build-report.json", release)
        self.assertIn("InternalTestUnsigned", release)
        self.assertIn("Production", release)
        self.assertIn("production_ready", release)
        self.assertIn("rfc3161_verified", release)
        self.assertIn("timestamp_digest_algorithm", release)
        self.assertIn("reportTemporaryPath", release)
        self.assertIn("Move-Item", release)
        self.assertLess(
            release.index("Remove-Item -LiteralPath $reportPath"),
            release.index("finalize-release-artifact.ps1"),
        )
        self.assertLess(
            release.index("$artifact = &"),
            release.index("$report = [ordered]"),
        )
        self.assertIn("Get-AuthenticodeSignature", finalizer)
        self.assertIn("TimeStamperCertificate", finalizer)
        self.assertIn("verify-rfc3161-timestamp.ps1", finalizer)
        self.assertIn("rfc3161_verified", finalizer)
        self.assertIn("CryptVerifyTimeStampSignature", rfc3161_verifier)
        self.assertIn("1.3.6.1.4.1.311.3.3.1", rfc3161_verifier)
        self.assertIn("1.2.840.113549.1.9.6", rfc3161_verifier)
        self.assertIn("1.3.6.1.4.1.311.2.4.1", rfc3161_verifier)
        self.assertIn("2.16.840.1.101.3.4.2.1", rfc3161_verifier)
        self.assertIn("GetSignature()", rfc3161_verifier)
        development_verifier = (ROOT / "scripts" / "verify-development.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("test-rfc3161-timestamp-verification.ps1", development_verifier)
        self.assertIn("signtool.exe", finalizer)
        self.assertIn("Get-StableArtifactEvidence", finalizer)
        self.assertIn("outside the source repository", finalizer)
        self.assertIn("$Product.product_version", staging)
        self.assertIn("$Product.build_id", staging)
        self.assertIn("$manifest.product_version", installer_builder)
        self.assertNotIn("'/DPRODUCT_VERSION=0.1.0'", installer_builder)
        self.assertIn('${PRODUCT_FILE_VERSION}', self.installer)

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
        self.assertIn(
            "[ValidateSet('PreInstall', 'Backup', 'Restore', 'Commit', 'Restart', 'Cleanup')]",
            self.maintenance,
        )
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
        self.assertNotIn("Stop-Process -Name", self.maintenance)

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
        staging_source = STAGING_SOURCE.read_text(encoding="utf-8")
        self.assertIn('"macsoft-server.db"', staging_source)
        self.assertIn('"state.db"', staging_source)
        self.assertIn("Forbidden state file included", staging_source)

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

    def test_installer_health_requires_exact_runtime_compatibility(self) -> None:
        self.assertIn('-ProgramRoot "$INSTDIR"', self.installer)
        self.assertIn("http://127.0.0.1:8643/api/status", self.verify_health)
        self.assertIn("$config.runtime_mode -eq 'config-only'", self.verify_health)
        self.assertIn("$product.runtime_base_version", self.verify_health)
        self.assertIn("$product.runtime_base_commit", self.verify_health)
        self.assertIn("$product.runtime_contract_version", self.verify_health)
        self.assertIn("$product.runtime_metadata_schema_version", self.verify_health)
        self.assertIn(
            "AI Service runtime compatibility handshake failed.",
            self.verify_health,
        )

    def test_overlay_update_has_program_files_recovery_without_programdata_rewrite(self) -> None:
        self.assertIn('-Action Backup', self.installer)
        self.assertIn('-Action Restore', self.installer)
        self.assertIn('-Action Commit', self.installer)
        self.assertIn('-Action Restart', self.installer)
        self.assertIn('"$APPDATA\\MacSoft Agent Recovery"', self.installer)
        self.assertIn("New-ProgramRecoveryBackup", self.maintenance)
        self.assertIn("Restore-ProgramRecoveryBackup", self.maintenance)
        self.assertIn("Remove-ProgramRecoveryBackup", self.maintenance)
        self.assertIn("Restart-ExistingService", self.maintenance)
        self.assertNotIn("RecoveryRoot = $DataRoot", self.maintenance)
        self.assertNotIn("Invoke-RobocopyChecked -Source $DataRoot", self.maintenance)


if __name__ == "__main__":
    unittest.main()
