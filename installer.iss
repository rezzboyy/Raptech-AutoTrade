; Inno Setup Script for X Trading Engine
; High-Performance MetaTrader 5 Algorithmic Trading Desktop Engine

#define MyAppName "X Trading Engine"
#define MyAppVersion "3.2.3"
#define MyAppPublisher "X Trading"
#define MyAppURL "https://github.com/rezzboyy/Raptech-AutoTrade"
#define MyAppExeName "XTradingEngine.exe"

[Setup]
; Unique AppId generated specifically for X Trading Engine
AppId={{B42E8D71-7A39-4E62-B93E-51C3D8B09E38}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Target Directory (Standard Auto Program Files)
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output Settings
OutputDir=dist
OutputBaseFilename=XTradingEngine_Setup_v{#MyAppVersion}
SetupIconFile=cpp\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Compression Settings (Maximum Ratio with LZMA2)
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Require 64-bit Windows
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

; Privileges (Dapat diinstal tanpa admin ke LocalAppData, atau dengan admin ke Program Files)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Seamless OTA & Auto Close Running Applications on Update
CloseApplications=force
CloseApplicationsFilter=*.exe
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Seluruh berkas biner standalone, runtime Qt, dan embedded Python engine
Source: "dist\XTradingEngine\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
