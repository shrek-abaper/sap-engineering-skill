; Inno Setup script for the self-contained sap-adt CLI (Windows x86_64).
;
; STATUS: IMPLEMENTED, NOT VERIFIED — no Windows build host was available in
; this workspace (see packaging/targets.json). Build with Inno Setup 6 on
; Windows after `tools/build_runtime.py` produced dist\runtime\windows-x86_64\sap-adt\.
;
; Design rules (spec §7.2):
;   - per-user install by default (no admin required); organization-wide
;     policies are respected, never bypassed
;   - post-install self-test uses the ABSOLUTE path of this install, never a
;     not-yet-refreshed PATH
;   - no passwords on command lines; configuration stays interactive/local
;   - uninstall does NOT remove the user's config (~/.sap-adt-cli) or
;     keystore entries
;   - handles paths with spaces / non-ASCII usernames (quoted ExpandConstant)

#define AppName "sap-adt"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppPublisher "shrek-abaper"
#define AppURL "https://github.com/shrek-abaper/sap-engineering-skill"

[Setup]
AppId={{9C9C0D2E-3F2A-4B1C-9E1A-5A0A0D7C1A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={userpf}\sap-adt
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\installers
OutputBaseFilename=sap-adt-{#AppVersion}-windows-x86_64-setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayName={#AppName}
; Do not let uninstall delete user configuration; only program files are removed.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; The onedir PyInstaller tree is the single runtime artifact (same one the
; npm channel and portable archive use).
Source: "..\..\dist\runtime\windows-x86_64\sap-adt\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "configure.cmd"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Configure sap-adt"; Filename: "{app}\configure.cmd"; Comment: "Interactive SAP connection setup (local, password never on the command line)"
Name: "{group}\Uninstall sap-adt"; Filename: "{uninstallexe}"

[Registry]
; Add {app} to the per-user PATH (no admin). User is told to restart their
; terminal/agent for PATH to refresh.
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath('{app}'); Flags: preservestringtype

[Run]
; Post-install self-test with the absolute path of THIS install.
Filename: "{app}\sap-adt.exe"; Parameters: "--version"; Description: "Self-test: sap-adt --version"; Flags: runhidden waituntilterminated
Filename: "{app}\sap-adt.exe"; Parameters: "credentials doctor"; Description: "Keystore backend diagnostics (no secrets shown)"; Flags: runhidden waituntilterminated skipifdoesntexist

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Uppercase(Param) + ';', ';' + Uppercase(OrigPath) + ';') = 0;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    MsgBox('sap-adt was installed per-user.' #13#10 #13#10
      + 'Next steps:' #13#10
      + '  1. Restart your terminal or agent so PATH refreshes.' #13#10
      + '  2. Run  sap-adt configure  for interactive SAP connection setup.' #13#10
      + '  3. Run  sap-adt credentials doctor  to see the keystore backend.',
      mbInformation, MB_OK);
  end;
end;
