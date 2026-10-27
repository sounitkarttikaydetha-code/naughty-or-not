; Clearance Check — Inno Setup Script
; Installs per-user to %LOCALAPPDATA%\Programs\ClearanceCheck with NO ADMIN RIGHTS required.

#define MyAppName "Clearance Check"
#define MyAppVersion "1.1.1"
#define MyAppPublisher "Compliance Engineering"
#define MyAppURL "https://github.com/organization/clearance-check"
#define MyAppExeName "Clearance Check.exe"

[Setup]
AppId={{8B264E24-F429-411B-A719-756D8D5A1102}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\ClearanceCheck
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=TERMS_OF_USE.txt
OutputDir=..\dist\installer
OutputBaseFilename=ClearanceCheck_Setup_v{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
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
; Main PyInstaller one-folder output
Source: "..\dist\ClearanceCheck\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\dist\NaughtyOrNot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; Bundled Seed Sanctions Lists
Source: "..\data\raw\*"; DestDir: "{app}\data\raw"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\data\aviation\*"; DestDir: "{app}\data\aviation"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\data\india\*"; DestDir: "{app}\data\india"; Flags: ignoreversion recursesubdirs createallsubdirs
; User Guide and Documentation
Source: "..\USER_GUIDE.pdf"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "TERMS_OF_USE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\User Guide (PDF)"; Filename: "{app}\USER_GUIDE.pdf"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Custom uninstaller step: Ask user whether to keep logs and reports (kept by default per SPEC / T7 B5)
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  KeepData: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\ClearanceCheck');
    if DirExists(DataDir) then
    begin
      KeepData := MsgBox('Would you like to keep your screening logs and compliance reports for audit retention?' + #13#10 +
                         'Locations: ' + DataDir + '\logs and \reports' + #13#10#13#10 +
                         '(Recommended: Yes to keep logs/reports, No to remove them)',
                         mbConfirmation, MB_YESNO or MB_DEFBUTTON1);
      if KeepData = IDNO then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
