function WithoutPathEntry(PathValue, Entry: string): string;
var
  Part: string;
  Separator: Integer;
  First: Boolean;
begin
  Result := PathValue;
  if Entry = '' then
    exit;
  Result := '';
  First := True;
  repeat
    Separator := Pos(';', PathValue);
    if Separator = 0 then
    begin
      Part := PathValue;
      PathValue := '';
    end
    else
    begin
      Part := Copy(PathValue, 1, Separator - 1);
      Delete(PathValue, 1, Separator);
    end;
    if CompareText(Trim(Part), Entry) <> 0 then
    begin
      if not First then
        Result := Result + ';';
      Result := Result + Part;
      First := False;
    end;
  until Separator = 0;
end;
