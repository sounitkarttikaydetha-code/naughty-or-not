; Clearance Check Canary — Inno Setup Script
; Installs per-user to %LOCALAPPDATA%\Programs\ClearanceCheckCanary with NO ADMIN RIGHTS required.
; Fully isolated from stable Clearance Check (%LOCALAPPDATA%\Programs\ClearanceCheck).

#define MyAppName "Clearance Check Canary"
#define MyAppVersion "2.0.1-canary.1"
#define MyAppPublisher "Compliance Engineering"
#define MyAppURL "https://github.com/organization/clearance-check"
#define MyAppExeName "Clearance Check Canary.exe"

[Setup]
AppId={{B42E7A91-8D3C-4E65-A259-866DE273D1E0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\ClearanceCheckCanary
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=TERMS_OF_USE.txt
OutputDir=..\dist\installer
OutputBaseFilename=ClearanceCheckCanary_Setup_v{#MyAppVersion}
SetupIconFile=..\assets\icon_canary.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\ClearanceCheckCanary\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\data\raw\*"; DestDir: "{app}\data\raw"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\data\aviation\*"; DestDir: "{app}\data\aviation"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\data\india\*"; DestDir: "{app}\data\india"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "TERMS_OF_USE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon_canary.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon_canary.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Isolated canary uninstaller: operates strictly on ClearanceCheckCanary data folder
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  KeepData: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\ClearanceCheckCanary');
    if DirExists(DataDir) then
    begin
      KeepData := MsgBox('Would you like to keep your Canary logs and test reports?' + #13#10 +
                         'Location: ' + DataDir + '\logs and \reports' + #13#10#13#10 +
                         '(Recommended: Yes to keep logs/reports, No to remove them)',
                         mbConfirmation, MB_YESNO or MB_DEFBUTTON1);
      if KeepData = IDNO then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
