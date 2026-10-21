; Inno Setup script — per-user install, no admin rights needed.
#define AppVersion GetEnv("DS_VERSION")
#if AppVersion == ""
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{9D2F3E4B-8E6A-4F9C-A04B-E8B6F2D3C4F5}
AppName=SuperDrag
AppVersion={#AppVersion}
AppPublisher=SuperDrag
DefaultDirName={localappdata}\Programs\SuperDrag
DefaultGroupName=SuperDrag
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=SuperDrag-Setup
SetupIconFile=..\dragshift\assets\superdrag.ico
UninstallDisplayIcon={app}\SuperDrag.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "autostart"; Description: "Start SuperDrag when I sign in to Windows"; Flags: checkedonce
Name: "contextmenu"; Description: "Add ""SuperDrag"" to the right-click menu for files"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\SuperDrag\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\SuperDrag"; Filename: "{app}\SuperDrag.exe"
Name: "{autodesktop}\SuperDrag"; Filename: "{app}\SuperDrag.exe"; Tasks: desktopicon
Name: "{usersendto}\SuperDrag"; Filename: "{app}\SuperDrag.exe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SuperDrag"; ValueData: """{app}\SuperDrag.exe"" --quiet"; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\*\shell\SuperDrag"; ValueType: string; ValueName: "MUIVerb"; ValueData: "SuperDrag…"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\SuperDrag"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\SuperDrag.exe"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\SuperDrag"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\SuperDrag\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SuperDrag.exe"" ""%1"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\SuperDrag"; Flags: uninsdeletekey

[Run]
Filename: "{app}\SuperDrag.exe"; Description: "Launch SuperDrag now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM SuperDrag.exe"; Flags: runhidden; RunOnceId: "KillSuperDrag"
