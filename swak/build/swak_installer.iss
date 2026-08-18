; SWAK Data Tools Runtime — Inno Setup Script
; Build (local):   iscc /DAppVersion=2.0.0 swak_installer.iss
; Build (CI):      ISCC.exe /DAppVersion=%VERSION% swak_installer.iss
; Output:          dist\SWAK_Runtime_Setup_v{AppVersion}.exe

; ── Version (از command line یا default) ─────────────────────────────────
#ifndef AppVersion
  #define AppVersion "2.0.0"
#endif

#define AppName      "SWAK Data Tools Runtime"
#define AppPublisher "SWAK Software"
#define AppURL       "https://swaksoft.com"
#define AppExeName   "swak_runtime.exe"
#define ServiceName  "SWAKRuntime"

[Setup]
AppId                    = {{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName                  = {#AppName}
AppVersion               = {#AppVersion}
AppPublisher             = {#AppPublisher}
AppPublisherURL          = {#AppURL}
AppSupportURL            = {#AppURL}/support
AppUpdatesURL            = {#AppURL}/download
DefaultDirName           = {autopf}\SWAK Runtime
DefaultGroupName         = SWAK Data Tools
AllowNoIcons             = yes
OutputDir                = ..\dist
OutputBaseFilename       = SWAK_Runtime_Setup_v{#AppVersion}
Compression              = lzma2/ultra64
SolidCompression         = yes
WizardStyle              = modern
PrivilegesRequired       = admin
MinVersion               = 10.0
ArchitecturesInstallIn64BitMode = x64
ChangesEnvironment       = yes
UninstallDisplayName     = SWAK Data Tools Runtime v{#AppVersion}

; اگر آیکون داری:
; SetupIconFile = assets\swak_icon.ico

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart";   Description: "Start SWAK Runtime automatically when Windows starts"; GroupDescription: "Additional tasks:"; Flags: checked
Name: "desktopicon"; Description: "Create desktop shortcut";                               GroupDescription: "Additional tasks:"

[Files]
; Main executable + all bundled files (PyInstaller one-file)
Source: "..\dist\swak_runtime.exe"; DestDir: "{app}"; Flags: ignoreversion

; .env template
Source: "..\server\.env.template"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist; DestName: ".env.template"

[Icons]
; Start Menu
Name: "{group}\SWAK Data Tools Runtime"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall SWAK Runtime";  Filename: "{uninstallexe}"

; Desktop (اختیاری)
Name: "{autodesktop}\SWAK Data Tools Runtime"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

; Startup (auto-start tray)
Name: "{userstartup}\SWAK Runtime"; Filename: "{app}\{#AppExeName}"; Tasks: autostart

[Run]
; 1. نصب Windows Service
Filename: "{app}\{#AppExeName}"; Parameters: "service install"; StatusMsg: "Installing SWAK Service..."; Flags: runhidden waituntilterminated

; 2. شروع service
Filename: "{app}\{#AppExeName}"; Parameters: "service start";   StatusMsg: "Starting SWAK Runtime...";   Flags: runhidden waituntilterminated

; 3. باز کردن tray app برای کاربر
Filename: "{app}\{#AppExeName}"; Parameters: "tray";            Description: "Launch SWAK Runtime tray app"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\{#AppExeName}"; Parameters: "service stop";   Flags: runhidden waituntilterminated
Filename: "{app}\{#AppExeName}"; Parameters: "service remove"; Flags: runhidden waituntilterminated

[Registry]
Root: HKLM; Subkey: "SOFTWARE\SWAK"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}";          Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\SWAK"; ValueType: string; ValueName: "Version";     ValueData: "{#AppVersion}"
Root: HKLM; Subkey: "SOFTWARE\SWAK"; ValueType: string; ValueName: "Port";        ValueData: "5000"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    { ساخت .env از template اگر وجود نداره }
    if not FileExists(ExpandConstant('{app}\.env')) then
      FileCopy(ExpandConstant('{app}\.env.template'),
               ExpandConstant('{app}\.env'), False);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  { حذف .env هنگام uninstall }
  if CurUninstallStep = usPostUninstall then
    DeleteFile(ExpandConstant('{app}\.env'));
end;
