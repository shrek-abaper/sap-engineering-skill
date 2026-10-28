; Exercises the production Pascal helper without modifying the user's PATH.
[Setup]
AppName=sap-adt installer PATH tests
AppVersion=0
DefaultDirName={tmp}\sap-adt-path-tests
CreateAppDir=no
Uninstallable=no
PrivilegesRequired=lowest
OutputBaseFilename=path-tests

[Code]
#include "..\..\packaging\windows\path.iss"

procedure Check(Input, Entry, Expected: string);
begin
  if WithoutPathEntry(Input, Entry) <> Expected then
    RaiseException('Unexpected PATH cleanup result for: ' + Input);
end;

function InitializeSetup(): Boolean;
begin
  Check('C:\one;C:\sap-adt;C:\two', 'C:\sap-adt', 'C:\one;C:\two');
  Check('C:\sap-adt;C:\two', 'C:\sap-adt', 'C:\two');
  Check('C:\one;C:\sap-adt', 'C:\sap-adt', 'C:\one');
  Check('C:\sap-adt', 'C:\sap-adt', '');
  Check('C:\one;C:\SAP-ADT;C:\two', 'C:\sap-adt', 'C:\one;C:\two');
  Check('C:\sap-adt-tools;C:\two', 'C:\sap-adt', 'C:\sap-adt-tools;C:\two');
  Check(';C:\one;; C:\sap-adt ;C:\two;', 'C:\sap-adt', ';C:\one;;C:\two;');
  Check(';C:\one;;', '', ';C:\one;;');
  Check('', 'C:\sap-adt', '');
  Log('Installer PATH cleanup tests passed.');
  Result := True;
end;
