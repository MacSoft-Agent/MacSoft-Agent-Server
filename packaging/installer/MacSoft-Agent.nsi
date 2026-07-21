Unicode true

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"
!include "x64.nsh"

!ifndef PAYLOAD_ROOT
  !error "PAYLOAD_ROOT is required."
!endif
!ifndef OUTPUT_FILE
  !error "OUTPUT_FILE is required."
!endif
!ifndef PRODUCT_VERSION
  !define PRODUCT_VERSION "0.1.0"
!endif

!define PRODUCT_NAME "MacSoft Agent"
!define SERVICE_NAME "MacSoftAgentHost"
!define FIREWALL_RULE "MacSoft Agent Server 8787"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\MacSoft Agent"
!define DESKTOP_SHORTCUT_NAME "MacSoft Server"

Name "${PRODUCT_NAME}"
OutFile "${OUTPUT_FILE}"
InstallDir "$PROGRAMFILES64\MacSoft Agent"
InstallDirRegKey HKLM "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 64
ShowInstDetails show
ShowUninstDetails show

VIProductVersion "0.1.0.0"
VIAddVersionKey /LANG=1033 "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey /LANG=1033 "FileDescription" "MacSoft Agent Windows Installer"
VIAddVersionKey /LANG=1033 "ProductVersion" "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1033 "FileVersion" "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1033 "CompanyName" "Mac Soft"
VIAddVersionKey /LANG=1033 "LegalCopyright" "Copyright (C) 2026 Mac Soft"

!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\desktop\MacSoft Agent.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch MacSoft Agent"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
UninstPage custom un.PurgePageCreate un.PurgePageLeave
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Var CommandExit
Var CommandOutput
Var PurgeCheckbox
Var PurgeData

!macro RunChecked Command FailureMessage
  nsExec::ExecToStack `${Command}`
  Pop $CommandExit
  Pop $CommandOutput
  DetailPrint "$CommandOutput"
  ${If} $CommandExit != 0
    MessageBox MB_ICONSTOP "${FailureMessage}$\r$\nExit code: $CommandExit"
    Abort
  ${EndIf}
!macroend

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "MacSoft Agent requires 64-bit Windows."
    Abort
  ${EndIf}
  SetRegView 64
  SetShellVarContext all
FunctionEnd

Function un.onInit
  SetRegView 64
  SetShellVarContext all
  StrCpy $PurgeData 0
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/PURGEDATA" $1
  ${IfNot} ${Errors}
    StrCpy $PurgeData 1
  ${EndIf}
FunctionEnd

Function un.PurgePageCreate
  ${If} $PurgeData == 1
    Abort
  ${EndIf}
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}
  ${NSD_CreateLabel} 0 0 100% 28u "MacSoft Agent data is preserved by default so a reinstall can restore settings and sessions."
  Pop $0
  ${NSD_CreateCheckbox} 0 38u 100% 28u "Remove all MacSoft Agent data, credentials, sessions, settings, and logs"
  Pop $PurgeCheckbox
  ${NSD_Uncheck} $PurgeCheckbox
  nsDialogs::Show
FunctionEnd

Function un.PurgePageLeave
  ${If} $PurgeData == 1
    Return
  ${EndIf}
  ${NSD_GetState} $PurgeCheckbox $0
  ${If} $0 == ${BST_CHECKED}
    MessageBox MB_ICONEXCLAMATION|MB_YESNO|MB_DEFBUTTON2 "This permanently removes all MacSoft Agent credentials, sessions, settings, logs, and runtime state. This action cannot be undone.$\r$\n$\r$\nContinue?" IDYES confirmed
    ${NSD_Uncheck} $PurgeCheckbox
    Abort
confirmed:
    StrCpy $PurgeData 1
  ${EndIf}
FunctionEnd

Section "Install MacSoft Agent" SEC_MAIN
  SetShellVarContext all
  SetRegView 64

  InitPluginsDir
  File /oname=$PLUGINSDIR\maintenance.ps1 "${__FILEDIR__}\maintenance.ps1"

  DetailPrint "Stopping the existing MacSoft Agent installation before payload replacement."
  !insertmacro RunChecked '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\maintenance.ps1" -Action PreInstall -ProgramRoot "$INSTDIR" -DataRoot "$APPDATA\MacSoft Agent" -PurgeData 0' "MacSoft Agent could not safely stop the existing installation. Close MacSoft Server and try again."

  SetOutPath "$INSTDIR"
  DetailPrint "Installing the verified MacSoft Agent payload."
  File /r "${PAYLOAD_ROOT}\*.*"

  CreateDirectory "$APPDATA\MacSoft Agent"
  !insertmacro RunChecked '"$SYSDIR\icacls.exe" "$APPDATA\MacSoft Agent" /inheritance:e /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-19:(OI)(CI)M" "*S-1-5-32-545:(OI)(CI)M"' "MacSoft Agent could not configure ProgramData permissions."

  SetOutPath "$INSTDIR"
  !insertmacro RunChecked '"$INSTDIR\python\python.exe" -B -m macsoft_runtime --mode packaged --program-root "$INSTDIR" --data-root "$APPDATA\MacSoft Agent" --initialize-only' "MacSoft Agent product initialization failed."

  nsExec::ExecToStack '"$SYSDIR\sc.exe" query ${SERVICE_NAME}'
  Pop $CommandExit
  Pop $CommandOutput
  DetailPrint "$CommandOutput"
  ${If} $CommandExit == 0
    !insertmacro RunChecked '"$INSTDIR\python\python.exe" -B -m macsoft_runtime.service --username "NT AUTHORITY\LocalService" --startup auto update' "MacSoft Agent Host service update failed."
  ${ElseIf} $CommandExit == 1060
    !insertmacro RunChecked '"$INSTDIR\python\python.exe" -B -m macsoft_runtime.service --username "NT AUTHORITY\LocalService" --startup auto install' "MacSoft Agent Host service registration failed."
  ${Else}
    MessageBox MB_ICONSTOP "MacSoft Agent could not determine the existing Host service state.$\r$\nExit code: $CommandExit"
    Abort
  ${EndIf}
  !insertmacro RunChecked '"$SYSDIR\reg.exe" add "HKLM\SYSTEM\CurrentControlSet\Services\${SERVICE_NAME}\PythonClass" /ve /t REG_SZ /d "macsoft_runtime.service.MacSoftAgentHostService" /f' "MacSoft Agent could not finalize its Host service registration."
  !insertmacro RunChecked '"$SYSDIR\sc.exe" sidtype ${SERVICE_NAME} unrestricted' "MacSoft Agent could not configure its service identity."
  !insertmacro RunChecked '"$SYSDIR\sc.exe" failure ${SERVICE_NAME} reset= 86400 actions= restart/5000/restart/15000/restart/60000' "MacSoft Agent could not configure service recovery."

  nsExec::ExecToLog '"$SYSDIR\netsh.exe" advfirewall firewall delete rule name="${FIREWALL_RULE}"'
  Pop $CommandExit
  !insertmacro RunChecked '"$SYSDIR\netsh.exe" advfirewall firewall add rule name="${FIREWALL_RULE}" dir=in action=allow program="$INSTDIR\python\python.exe" protocol=TCP localport=8787 profile=domain,private edge=no enable=yes' "MacSoft Agent could not create the Server firewall rule."

  !insertmacro RunChecked '"$SYSDIR\sc.exe" start ${SERVICE_NAME}' "MacSoft Agent Host service could not be started."

  File /oname=$PLUGINSDIR\verify-health.ps1 "${__FILEDIR__}\verify-health.ps1"
  !insertmacro RunChecked '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\verify-health.ps1"' "MacSoft Agent services did not become healthy within the installation timeout."

  CreateDirectory "$SMPROGRAMS\MacSoft Agent"
  CreateShortcut "$SMPROGRAMS\MacSoft Agent\MacSoft Agent.lnk" "$INSTDIR\desktop\MacSoft Agent.exe" "" "$INSTDIR\desktop\MacSoft Agent.exe" 0
  Delete "$DESKTOP\MacSoft Agent.lnk"
  CreateShortcut "$DESKTOP\${DESKTOP_SHORTCUT_NAME}.lnk" "$INSTDIR\desktop\MacSoft Agent.exe" "" "$INSTDIR\desktop\MacSoft Agent.exe" 0

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "Publisher" "Mac Soft"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\desktop\MacSoft Agent.exe"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair" 1
SectionEnd

Function .onInstFailed
  DetailPrint "Rolling back the incomplete MacSoft Agent installation."
  IfFileExists "$PLUGINSDIR\maintenance.ps1" 0 cleanup_done
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\maintenance.ps1" -Action Cleanup -ProgramRoot "$INSTDIR" -DataRoot "$APPDATA\MacSoft Agent" -PurgeData 0'
  Pop $CommandExit
  Pop $CommandOutput
  DetailPrint "$CommandOutput"
  ${If} $CommandExit == 3010
    SetRebootFlag true
  ${ElseIf} $CommandExit != 0
    DetailPrint "Rollback cleanup failed with exit code $CommandExit; uninstall registration is retained when present."
    Return
  ${EndIf}
cleanup_done:
  Delete "$DESKTOP\${DESKTOP_SHORTCUT_NAME}.lnk"
  Delete "$DESKTOP\MacSoft Agent.lnk"
  RMDir /r "$SMPROGRAMS\MacSoft Agent"
  Delete /REBOOTOK "$INSTDIR\Uninstall.exe"
  RMDir /r /REBOOTOK "$INSTDIR"
  DeleteRegKey HKLM "${UNINSTALL_KEY}"
FunctionEnd

Section "Uninstall"
  SetShellVarContext all
  SetRegView 64

  InitPluginsDir
  File /oname=$PLUGINSDIR\maintenance.ps1 "${__FILEDIR__}\maintenance.ps1"
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\maintenance.ps1" -Action Cleanup -ProgramRoot "$INSTDIR" -DataRoot "$APPDATA\MacSoft Agent" -PurgeData $PurgeData'
  Pop $CommandExit
  Pop $CommandOutput
  DetailPrint "$CommandOutput"
  ${If} $CommandExit == 3010
    SetRebootFlag true
  ${ElseIf} $CommandExit != 0
    MessageBox MB_ICONSTOP "MacSoft Agent cleanup could not be completed or safely scheduled.$\r$\nExit code: $CommandExit$\r$\n$\r$\nThe uninstall registration and product files were retained."
    Abort
  ${EndIf}

  Delete "$DESKTOP\${DESKTOP_SHORTCUT_NAME}.lnk"
  Delete "$DESKTOP\MacSoft Agent.lnk"
  RMDir /r "$SMPROGRAMS\MacSoft Agent"
  Delete /REBOOTOK "$INSTDIR\Uninstall.exe"
  RMDir /r /REBOOTOK "$INSTDIR"
  DeleteRegKey HKLM "${UNINSTALL_KEY}"
  IfRebootFlag 0 +2
    MessageBox MB_ICONINFORMATION "MacSoft Agent cleanup has been safely scheduled. Restart Windows to finish removing locked files or a service marked for deletion."
SectionEnd
