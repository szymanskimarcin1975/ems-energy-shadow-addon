# Windows built-in PowerShell + existing OpenSSH only. No passwords/tokens, no
# ExecutionPolicy bypass, no Core stop/start, no inverter or .storage operations.
[CmdletBinding()]
param(
  [ValidateSet('Prepare','Apply','Rollback')][string]$Mode='Prepare',
  [string]$HostName,
  [int]$Port=2222,
  [string]$BackupSlug,
  [string]$BackupDirectory
)
$ErrorActionPreference='Stop'
if (!$HostName) {$HostName=Read-Host 'Existing HA SSH hostname or IP'}
if ($HostName -notmatch '^[A-Za-z0-9][A-Za-z0-9.:-]*$' -or $Port -lt 1 -or $Port -gt 65535) {throw 'Invalid SSH target'}
if ($Mode -ne 'Rollback') {
  if (!$BackupSlug) {$BackupSlug=Read-Host 'Completed FULL Supervisor backup slug'}
  if ($BackupSlug -notmatch '^[a-f0-9]{8}$') {throw 'Invalid backup slug'}
}
$Target='root@'+$HostName
function Remote([string]$Command) {
  $out=& ssh -p $Port $Target $Command
  if ($LASTEXITCODE -ne 0) {throw 'SSH command failed; do not restart Core after partial Apply'}
  return ($out -join "`n")
}
function Unwrap-Response($Object) {if ($null -ne $Object.data) {return $Object.data};return $Object}
if ($Mode -ne 'Rollback') {
$Backup=Unwrap-Response ((Remote "ha backups info $BackupSlug --raw-json")|ConvertFrom-Json)
if ($Backup.slug -ne $BackupSlug -or $Backup.type -ne 'full' -or !$Backup.homeassistant -or !($Backup.size -gt 0)) {
  throw 'Full completed backup metadata not confirmed; no component change'
}
}
$Source='/config/custom_components/solaredge_modbus_multi'
$OriginalHub='512fe7b3f7d58735f210fd7ed6f87c15b3acc6f4c1c4d3a55070d9f9bdefa6c4'
$OriginalManifest='23ba7cc928c79dfaea183b568bfed04160ab4890d28a415071327cbe83b9bdcc'
function HashRemote([string]$Path) {return (Remote "sha256sum '$Path'").Split(' ')[0].Trim()}
if ($Mode -eq 'Prepare') {
  if ((HashRemote "$Source/hub.py") -ne $OriginalHub -or (HashRemote "$Source/manifest.json") -ne $OriginalManifest) {
    throw 'Installed source differs from reviewed4.0.4; refuse patch, preserve it for review'
  }
  $Stamp=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmss')
  $BackupDirectory='/config/ems_companion_backups/'+$Stamp
  # Code only. Active SQLite, Recorder, .storage and addon/data are untouched.
  Remote "set -e; test -z `"`$(find '$Source' -type l -print -quit)`"; mkdir -p /config/ems_companion_backups; mkdir '$BackupDirectory'; cp -a '$Source' '$BackupDirectory/component'; cd '$Source'; find . -type f ! -path '*/__pycache__/*' -exec sha256sum {} ';' > '$BackupDirectory/SHA256SUMS'; cd '$BackupDirectory/component'; sha256sum -c ../SHA256SUMS" | Write-Output
  $Local=Join-Path $PSScriptRoot ('actual-installed-backup-'+$Stamp)
  & scp -P $Port -r "${Target}:$BackupDirectory" $Local
  if ($LASTEXITCODE -ne 0) {throw 'Independent backup download failed; no Apply'}
  foreach ($line in Get-Content (Join-Path $Local 'SHA256SUMS')) {
    if ($line -notmatch '^([a-f0-9]{64})\s+\./(.+)$') {throw 'Unexpected hash manifest'}
    $Expected=$Matches[1];$Relative=$Matches[2]
    if ($Relative -match '(^|/)\.\.(/|$)' -or [IO.Path]::IsPathRooted($Relative)) {throw 'Unsafe manifest path'}
    $Actual=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path (Join-Path $Local 'component') $Relative)).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected) {throw 'Downloaded actual component hash mismatch'}
  }
  @{backup_directory=$BackupDirectory;backup_slug=$BackupSlug;original_hub=$OriginalHub;original_manifest=$OriginalManifest} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $PSScriptRoot 'prepared.json')
  Write-Output 'PREPARED: actual installed source backed up on HA and Windows, SHA256 verified. No installation or restart.'
  return
}
$Plan=Get-Content (Join-Path $PSScriptRoot 'prepared.json') -Raw|ConvertFrom-Json
if (!$BackupDirectory) {$BackupDirectory=$Plan.backup_directory}
if ($BackupDirectory -notmatch '^/config/ems_companion_backups/[0-9]{8}T[0-9]{6}$') {throw 'Unsafe backup path'}
$Core=Unwrap-Response ((Remote 'ha core info --raw-json')|ConvertFrom-Json)
if ($Core.state -ne 'stopped') {throw 'Core must already be stopped in an APPROVED maintenance window; script never stops it'}
Remote "cd '$BackupDirectory/component'; sha256sum -c ../SHA256SUMS" | Write-Output
if ($Mode -eq 'Apply') {
  if ((HashRemote "$Source/hub.py") -ne $OriginalHub -or (HashRemote "$Source/manifest.json") -ne $OriginalManifest) {throw 'Installed source changed after Prepare'}
  $Payload=Join-Path $PSScriptRoot 'payload'
  $Hashes=Get-Content (Join-Path $Payload 'SHA256.json') -Raw|ConvertFrom-Json
  foreach ($Name in @('hub.py','manifest.json')) {
    if ((Get-FileHash (Join-Path $Payload $Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Hashes.$Name) {throw 'Payload SHA256 mismatch'}
  }
  Remote "mkdir -p '$BackupDirectory/staging'" | Out-Null
  & scp -P $Port (Join-Path $Payload 'hub.py') (Join-Path $Payload 'manifest.json') "${Target}:$BackupDirectory/staging/"
  if ($LASTEXITCODE -ne 0) {throw 'Payload transfer failed'}
  foreach ($Name in @('hub.py','manifest.json')) {
    if ((HashRemote "$BackupDirectory/staging/$Name") -ne $Hashes.$Name) {throw 'Transferred payload SHA256 mismatch'}
  }
  foreach ($Name in @('hub.py','manifest.json')) {
    Remote "set -e; cp -p '$Source/$Name' '$Source/$Name.ems-tmp'; cat '$BackupDirectory/staging/$Name' > '$Source/$Name.ems-tmp'; mv '$Source/$Name.ems-tmp' '$Source/$Name'" | Out-Null
  }
  foreach ($Name in @('hub.py','manifest.json')) {
    if ((HashRemote "$Source/$Name") -ne $Hashes.$Name) {throw 'Installed payload hash mismatch; leave Core stopped'}
  }
  Write-Output 'APPLIED CODE ONLY. Core remains stopped. Verify hashes and approved recovery conditions before starting it. Entry opt-in is NOT changed.'
} else {
  $RecoveryStamp=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmss')
  Remote "set -e; cp -a '$BackupDirectory/component' '$BackupDirectory/recovery-$RecoveryStamp'; mv '$Source' '$BackupDirectory/failed-$RecoveryStamp'; mv '$BackupDirectory/recovery-$RecoveryStamp' '$Source'; cd '$Source'; sha256sum -c '$BackupDirectory/SHA256SUMS'" | Write-Output
  if ((HashRemote "$Source/hub.py") -ne $OriginalHub -or (HashRemote "$Source/manifest.json") -ne $OriginalManifest) {throw 'Recovery hash mismatch; leave Core stopped'}
  Write-Output 'ORIGINAL4.0.4 CODE RESTORED. No .storage or SQLite restoration; Core remains stopped.'
}
