; DualSensePilot kurulum sihirbazi (Inno Setup 6)
#define AppName "DualSensePilot"
#define AppVersion "1.0.0"
#define AppExe "DualSensePilot.exe"

[Setup]
AppId={{B7D3C9A2-5E41-4F6B-9A0C-DS5STUDIO0001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=DualSensePilot
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
; Kullanici kurulum klasorunu secebilsin
DisableDirPage=no
DisableProgramGroupPage=yes
AllowNoIcons=yes
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
SetupIconFile=assets\app.ico
OutputDir=installer_out
OutputBaseFilename=DualSensePilot_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Surucu kurulumu (HidHide/ViGEmBus) yonetici izni gerektirir; kurulum basindan
; itibaren UAC ile yukseltilir, aksi halde icerideki surucu yukleyicileri
; "Erisim engellendi" verebilir.
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek görevler:"
Name: "autostart"; Description: "Windows ile birlikte başlat (tepside küçültülmüş)"; GroupDescription: "Ek görevler:"; Flags: unchecked

[Files]
Source: "dist\DualSensePilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Surucu kurulumlari Program Files altindan degil, yazma izni olan {tmp}'den
; calistirilir (yoksa ic self-extract/guncelleyici adimlari "Erisim engellendi" verir).
Source: "tools\HidHide_1.5.230_x64.exe"; DestDir: "{tmp}"; Flags: dontcopy
Source: "tools\ViGEmBus_1.22.0_x64_x86_arm64.exe"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName} kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DualSensePilot"; ValueData: """{app}\{#AppExe}"" --minimized"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
; Eksik olan sürücüler kuruluma otomatik dahil edilir (kullanıcı uygulama içinden ayrıca indirmez).
; Gerçek kurulumları CurStepChanged ({tmp}'den çalıştırmak için) [Code] bölümünde yapılır.
Filename: "{app}\{#AppExe}"; Description: "{#AppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Calisan uygulamayi kapat
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "KillApp"

[Code]
function NeedViGEm: Boolean;
begin
  Result := not RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\ViGEmBus');
end;

function NeedHidHide: Boolean;
begin
  Result := not RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\HidHide');
end;

procedure InstallDriver(const FileName, Params, StatusMsg: string);
var
  ResultCode: Integer;
  TmpPath: string;
begin
  WizardForm.StatusLabel.Caption := StatusMsg;
  WizardForm.StatusLabel.Update;
  ExtractTemporaryFile(FileName);
  TmpPath := ExpandConstant('{tmp}\') + FileName;
  { ShellExec (Exec degil) kullanilir: dosyanin kendi manifestosundeki
    "requireAdministrator" talebiyle gerekirse UAC istegini kendisi tetikler. }
  if not ShellExec('', TmpPath, Params, '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then
    Log('Surucu kurulumu baslatilamadi: ' + FileName);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if NeedHidHide then
      InstallDriver('HidHide_1.5.230_x64.exe', '/passive /norestart', 'HidHide sürücüsü kuruluyor...');
    if NeedViGEm then
      InstallDriver('ViGEmBus_1.22.0_x64_x86_arm64.exe', '/passive /norestart', 'ViGEmBus sürücüsü kuruluyor...');
  end;
end;
