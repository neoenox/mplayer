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
PrivilegesRequired=admin
; 非管理者インストールを許可すると HKLM 固定の関連付け登録が失敗するため無効化
MinVersion=10.0

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"; Languages: japanese
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional tasks:"; Languages: english
Name: "associations"; Description: "動画ファイルをこのアプリで開く (既定のアプリの候補に登録)"; GroupDescription: "追加タスク:"; Languages: japanese
Name: "associations"; Description: "Associate video files with this app"; GroupDescription: "Additional tasks:"; Languages: english

[Files]
Source: "{#RepoRoot}\dist\mplayer\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Registry]
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp4"; ValueData: "mplayer.mp4"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mp4"; ValueData: ""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mkv"; ValueData: "mplayer.mkv"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mkv"; ValueData: ""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".avi"; ValueData: "mplayer.avi"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe\SupportedTypes"; ValueType: string; ValueName: ".avi"; ValueData: ""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mov"; ValueData: "mplayer.mov"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mov"; ValueData: ""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".webm"; ValueData: "mplayer.webm"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe\SupportedTypes"; ValueType: string; ValueName: ".webm"; ValueData: ""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m4v"; ValueData: "mplayer.m4v"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe\SupportedTypes"; ValueType: string; ValueName: ".m4v"; ValueData: ""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpg"; ValueData: "mplayer.mpg"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mpg"; ValueData: ""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpeg"; ValueData: "mplayer.mpeg"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mpeg"; ValueData: ""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wmv"; ValueData: "mplayer.wmv"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe\SupportedTypes"; ValueType: string; ValueName: ".wmv"; ValueData: ""; Tasks: associations
; Windows の「既定のアプリ」画面にアプリを表示するための登録
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "シンプル動画プレイヤー"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "シンプル動画プレイヤー"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\mplayer\Capabilities"; ValueType: string; ValueName: "ApplicationIcon"; ValueData: "{app}\{#AppExeName},0"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\RegisteredApplications"; ValueType: string; ValueName: "mplayer"; ValueData: "SOFTWARE\mplayer\Capabilities"; Flags: uninsdeletevalue; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe"; ValueType: string; ValueName: ""; ValueData: "シンプル動画プレイヤー"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "シンプル動画プレイヤー"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\Applications\mplayer.exe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer\FileAssociations"; ValueType: string; ValueName: ".mp4"; ValueData: "mplayer.mp4"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mp4"; ValueType: string; ValueName: ""; ValueData: "シンプル動画プレイヤー 動画ファイル"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mp4\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mp4\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer\FileAssociations"; ValueType: string; ValueName: ".mkv"; ValueData: "mplayer.mkv"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mkv"; ValueType: string; ValueName: ""; ValueData: "シンプル動画プレイヤー 動画ファイル"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mkv\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mkv\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer\FileAssociations"; ValueType: string; ValueName: ".avi"; ValueData: "mplayer.avi"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.avi"; ValueType: string; ValueName: ""; ValueData: "シンプル動画プレイヤー 動画ファイル"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.avi\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.avi\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer\FileAssociations"; ValueType: string; ValueName: ".mov"; ValueData: "mplayer.mov"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mov"; ValueType: string; ValueName: ""; ValueData: "シンプル動画プレイヤー 動画ファイル"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mov\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mov\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer\FileAssociations"; ValueType: string; ValueName: ".webm"; ValueData: "mplayer.webm"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.webm"; ValueType: string; ValueName: ""; ValueData: "シンプル動画プレイヤー 動画ファイル"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.webm\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.webm\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer\FileAssociations"; ValueType: string; ValueName: ".m4v"; ValueData: "mplayer.m4v"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.m4v"; ValueType: string; ValueName: ""; ValueData: "シンプル動画プレイヤー 動画ファイル"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.m4v\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.m4v\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer\FileAssociations"; ValueType: string; ValueName: ".mpg"; ValueData: "mplayer.mpg"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mpg"; ValueType: string; ValueName: ""; ValueData: "シンプル動画プレイヤー 動画ファイル"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mpg\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mpg\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer\FileAssociations"; ValueType: string; ValueName: ".mpeg"; ValueData: "mplayer.mpeg"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mpeg"; ValueType: string; ValueName: ""; ValueData: "シンプル動画プレイヤー 動画ファイル"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mpeg\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.mpeg\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer\FileAssociations"; ValueType: string; ValueName: ".wmv"; ValueData: "mplayer.wmv"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.wmv"; ValueType: string; ValueName: ""; ValueData: "シンプル動画プレイヤー 動画ファイル"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.wmv\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associations
Root: HKLM; Subkey: "SOFTWARE\Classes\mplayer.wmv\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associations

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{#AppName} をアンインストール"; Filename: "{uninstallexe}"; Languages: japanese
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"; Languages: english
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
