; Veet installer script for Inno Setup 6.x
; Compile (CPU):  iscc.exe packaging\installer.iss
; Compile (GPU):  iscc.exe /DBuildTarget=GPU packaging\installer.iss
; Free download:  https://jrsoftware.org/isdl.php

#ifndef BuildTarget
  #define BuildTarget "CPU"
#endif

#define MyAppName      "Veet"
#define MyAppVersion   "0.2.1"
#define MyAppPublisher "VL Media"
#define MyAppURL       "https://veet.app"
#define MyAppExeName   "Veet.exe"

[Setup]
AppId={{8D5A9C8B-4E2A-4D9F-9F2A-D6E7A1B2C3D4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=Veet-Setup-{#BuildTarget}-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\icon.ico
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; \
    GroupDescription: "Additional shortcuts:";    Flags: unchecked

[Files]
Source: "..\dist\Veet\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";          Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";    Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Auto-start: always installed so Veet launches every time Windows starts.
Name: "{userstartup}\{#MyAppName}";    Filename: "{app}\{#MyAppExeName}"

[Run]
; Launch Veet automatically when the installer finishes (no checkbox).
Filename: "{app}\{#MyAppExeName}"; Flags: nowait runasoriginaluser shellexec skipifsilent

[UninstallDelete]
; Wipe app-data on uninstall (log, generated chimes). User's HF model cache
; in ~/.cache/huggingface is left intact intentionally.
Type: filesandordirs; Name: "{localappdata}\{#MyAppName}"
