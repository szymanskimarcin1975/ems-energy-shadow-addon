# Real local filesystem Apply/Rollback, MOCKED OpenSSH and Supervisor only.
$ErrorActionPreference='Stop'
$Repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$Script=Join-Path $Repo 'tools/installation/EMS-Companion.ps1'
$Tokens=$null;$Errors=$null
[System.Management.Automation.Language.Parser]::ParseFile($Script,[ref]$Tokens,[ref]$Errors)|Out-Null
if ($Errors.Count) {throw ($Errors|Out-String)}
$Source=(Resolve-Path $env:SOLAREDGE_SOURCE).Path
$TestRoot=Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
$Runner=Join-Path $TestRoot 'runner'
$global:Sandbox=$TestRoot
$Installed=Join-Path $TestRoot 'config/custom_components/solaredge_modbus_multi'
New-Item -ItemType Directory (Split-Path $Installed)|Out-Null
Copy-Item -Recurse $Source $Installed
'actual installed local file'|Set-Content (Join-Path $Installed 'local-marker.txt')
$Artifact=Join-Path $TestRoot 'artifacts'
& python (Join-Path $Repo 'tools/installation/prepare_candidate.py') --solaredge-source $Source --output $Artifact
if ($LASTEXITCODE) {throw 'Fixture packaging failed'}
Expand-Archive (Join-Path $Artifact 'ems-companion-windows-installer.zip') $Runner
$TestScript=Join-Path $Runner 'EMS-Companion.ps1'
$global:FullBackupForTest=$true
$global:CoreStateForTest='started'
$global:SSHCommandsForTest=@()
function global:ssh {
  $cmd=[string]$args[-1];$global:SSHCommandsForTest+=$cmd
  if ($cmd -like 'ha backups info*') {
    @{data=@{slug='deadbeef';type=$(if($global:FullBackupForTest){'full'}else{'partial'});homeassistant=@{version='test'};size=10}}|ConvertTo-Json -Depth 3 -Compress
  } elseif ($cmd -eq 'ha core info --raw-json') {
    @{data=@{state=$global:CoreStateForTest}}|ConvertTo-Json -Depth 3 -Compress
  } else {
    # Run the exact installer's filesystem commands only inside an isolated tree.
    if ($cmd -notmatch '/config/' -or $cmd -match 'ha core (stop|start|restart)|\.storage|/data/') {throw 'Unexpected mocked SSH operation'}
    $localCommand=$cmd.Replace('/config/',$global:Sandbox+'/config/')
    & bash -c $localCommand
    if ($LASTEXITCODE) {throw 'Isolated filesystem operation failed'}
  }
  $global:LASTEXITCODE=0
}
function global:scp {
  $dest=[string]$args[-1]
  if ($dest -match ':/config/') {
    $localDest=($dest -split ':',2)[1].Replace('/config/',$global:Sandbox+'/config/')
    foreach ($arg in $args) {if (Test-Path -LiteralPath $arg -PathType Leaf) {Copy-Item -LiteralPath $arg -Destination $localDest}}
  } else {
    $remote=[string]$args[-2]
    if ($remote -notmatch ':/config/ems_companion_backups/') {throw 'Unexpected mocked SCP source'}
    $localSource=($remote -split ':',2)[1].Replace('/config/',$global:Sandbox+'/config/')
    Copy-Item -Recurse $localSource $dest
  }
  $global:LASTEXITCODE=0
}
try {
  & $TestScript -Mode Prepare -HostName 'isolated.invalid' -BackupSlug 'deadbeef'
  if (!(Test-Path (Join-Path $Runner 'prepared.json'))) {throw 'Prepare did not save recovery plan'}
  $Local=(Get-ChildItem -Directory $Runner -Filter 'actual-installed-backup-*').FullName
  if (!(Test-Path (Join-Path $Local 'component/local-marker.txt'))) {throw 'Actual independent backup missing'}
  $Failed=$false
  try {& $TestScript -Mode Apply -HostName 'isolated.invalid' -BackupSlug 'deadbeef'}
  catch {if ($_.Exception.Message -notmatch 'Core must already be stopped') {throw};$Failed=$true}
  if (!$Failed) {throw 'Live Core was not fenced'}
  $global:FullBackupForTest=$false;$Failed=$false
  try {& $TestScript -Mode Prepare -HostName 'isolated.invalid' -BackupSlug 'deadbeef'}
  catch {if ($_.Exception.Message -notmatch 'Full completed backup metadata not confirmed') {throw};$Failed=$true}
  if (!$Failed) {throw 'Partial backup was accepted'}
  if ($global:SSHCommandsForTest | Where-Object {$_ -match 'mv |staging'}) {throw 'Refusal path made a write'}
  $global:FullBackupForTest=$true;$global:CoreStateForTest='stopped'
  $Original=(Get-FileHash (Join-Path $Installed 'hub.py')).Hash
  $Sensor=(Get-FileHash (Join-Path $Installed 'sensor.py')).Hash
  & $TestScript -Mode Apply -HostName 'isolated.invalid' -BackupSlug 'deadbeef'
  if ((Get-FileHash (Join-Path $Installed 'hub.py')).Hash -eq $Original) {throw 'Apply did not replace hub'}
  if ((Get-FileHash (Join-Path $Installed 'sensor.py')).Hash -ne $Sensor) {throw 'Apply changed unrelated code'}
  if ((Get-Content (Join-Path $Installed 'manifest.json') -Raw|ConvertFrom-Json).version -ne '4.0.4+ems.1') {throw 'Wrong installed version'}
  $global:FullBackupForTest=$false # Code recovery must not depend on a full archive query.
  & $TestScript -Mode Rollback -HostName 'isolated.invalid'
  if ((Get-FileHash (Join-Path $Installed 'hub.py')).Hash -ne $Original) {throw 'Actual code recovery failed'}
  if (!(Test-Path (Join-Path $Installed 'local-marker.txt'))) {throw 'Recovery lost actual installed file'}
  if ($global:SSHCommandsForTest | Where-Object {$_ -match 'ha core (stop|start|restart)|\.storage|/data/'}) {throw 'Forbidden operation'}
  Write-Output 'INSTALLER_PARSE_BACKUP_SHA256_APPLY_ROLLBACK_AND_REFUSAL_PASS (LOCAL_FILESYSTEM_MOCK_SSH_ONLY)'
} finally {
  Remove-Item -Recurse -Force $TestRoot
  Remove-Item Function:\ssh;Remove-Item Function:\scp
}
