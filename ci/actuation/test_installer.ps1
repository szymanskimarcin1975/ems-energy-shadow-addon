# Executes Prepare and refusal paths using mocked OpenSSH, no network/HA access.
$ErrorActionPreference='Stop'
$Repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$Script=Join-Path $Repo 'tools/installation/EMS-Companion.ps1'
$Tokens=$null;$Errors=$null
[System.Management.Automation.Language.Parser]::ParseFile($Script,[ref]$Tokens,[ref]$Errors)|Out-Null
if ($Errors.Count) {throw ($Errors|Out-String)}
$Source=(Resolve-Path $env:SOLAREDGE_SOURCE).Path
$TestRoot=Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
$Runner=Join-Path $TestRoot 'runner';New-Item -ItemType Directory $Runner|Out-Null
$Installed=Join-Path $TestRoot 'actual-installed';Copy-Item -Recurse $Source $Installed
$global:RemoteBackup=Join-Path $TestRoot 'remote-backup'
$global:InstalledForTest=$Installed
$global:FullBackupForTest=$true
$global:CoreStateForTest='started'
$global:SSHCommandsForTest=@()
$TestScript=Join-Path $Runner 'EMS-Companion.ps1';Copy-Item $Script $TestScript
function global:ssh {
  $cmd=[string]$args[-1];$global:SSHCommandsForTest+=$cmd
  if ($cmd -like 'ha backups info*') {
    @{data=@{slug='deadbeef';type=$(if($global:FullBackupForTest){'full'}else{'partial'});homeassistant=@{version='test'};size=10}}|ConvertTo-Json -Depth 3 -Compress
  } elseif ($cmd -eq 'ha core info --raw-json') {
    @{data=@{state=$global:CoreStateForTest}}|ConvertTo-Json -Depth 3 -Compress
  } elseif ($cmd -like 'sha256sum *') {
    $name=if($cmd -like '*hub.py*'){'hub.py'}else{'manifest.json'}
    ((Get-FileHash (Join-Path $global:InstalledForTest $name) -Algorithm SHA256).Hash.ToLowerInvariant())+'  '+$name
  } elseif ($cmd -like '*find . -type f*') {
    New-Item -ItemType Directory $global:RemoteBackup|Out-Null
    $dst=Join-Path $global:RemoteBackup 'component';Copy-Item -Recurse $global:InstalledForTest $dst
    $Lines=Get-ChildItem -Recurse -File $dst | Where-Object {$_.FullName -notmatch '__pycache__'} | ForEach-Object {
      $relative=[IO.Path]::GetRelativePath($dst,$_.FullName).Replace('\','/')
      (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()+'  ./'+$relative
    }
    $Lines|Set-Content (Join-Path $global:RemoteBackup 'SHA256SUMS')
    'actual code backup OK'
  } elseif ($cmd -like '*sha256sum -c*') {'hashes OK'}
  else {throw 'Unexpected mocked SSH operation: '+$cmd}
  $global:LASTEXITCODE=0
}
function global:scp {
  $destination=[string]$args[-1]
  Copy-Item -Recurse $global:RemoteBackup $destination
  $global:LASTEXITCODE=0
}
try {
  & $TestScript -Mode Prepare -HostName 'isolated.invalid' -BackupSlug 'deadbeef'
  if (!(Test-Path (Join-Path $Runner 'prepared.json'))) {throw 'Prepare did not save recovery plan'}
  $Local=(Get-ChildItem -Directory $Runner -Filter 'actual-installed-backup-*').FullName
  if (!(Test-Path (Join-Path $Local 'component/hub.py'))) {throw 'Independent actual backup missing'}
  $Failed=$false
  try {& $TestScript -Mode Apply -HostName 'isolated.invalid' -BackupSlug 'deadbeef'}
  catch {if ($_.Exception.Message -notmatch 'Core must already be stopped') {throw};$Failed=$true}
  if (!$Failed) {throw 'Live Core was not fenced'}
  $global:FullBackupForTest=$false;$Failed=$false
  try {& $TestScript -Mode Prepare -HostName 'isolated.invalid' -BackupSlug 'deadbeef'}
  catch {if ($_.Exception.Message -notmatch 'Full completed backup metadata not confirmed') {throw};$Failed=$true}
  if (!$Failed) {throw 'Partial backup was accepted'}
  if ($global:SSHCommandsForTest | Where-Object {$_ -match 'ha core (stop|start|restart)|mv |staging|\.storage|/data/'}) {throw 'Refusal test made an unsafe operation'}
  Write-Output 'INSTALLER_PARSE_ACTUAL_CODE_BACKUP_SHA256_CORE_AND_BACKUP_GUARDS_PASS (MOCK_SSH_ONLY)'
} finally {
  Remove-Item -Recurse -Force $TestRoot
  Remove-Item Function:\ssh;Remove-Item Function:\scp
}
