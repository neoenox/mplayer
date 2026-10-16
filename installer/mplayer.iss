; シンプル動画プレイヤー Inno Setup スクリプト
; ビルドは tools/make_installer.py から実行する (AppVersion / RepoRoot を渡す)。
; このファイルは UTF-8 (BOM 付き) で保存すること。

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef RepoRoot
  #define RepoRoot ".."
#endif

#define AppName "シンプル動画プレイヤー"
#define AppExeName "mplayer.exe"

[Setup]
AppId={{7E4C2E9A-2F3B-4C5D-9A6E-1B2C3D4E5F60}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=mplayer
AppPublisherURL=https://github.com/neoenox/mplayer
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#RepoRoot}\dist\installer
OutputBaseFilename=mplayer-setup-{#AppVersion}
SetupIconFile={#RepoRoot}\assets\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"; Languages: japanese
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional tasks:"; Languages: english

[Files]
Source: "{#RepoRoot}\dist\mplayer\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{#AppName} をアンインストール"; Filename: "{uninstallexe}"; Languages: japanese
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"; Languages: english
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
