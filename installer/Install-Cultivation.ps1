[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ServerRoot,
    [Parameter(Mandatory)][string]$ClientRoot,
    [string]$ServerDataRoot,
    [string]$BackupRoot = 'F:\JestokyCraft Backups',
    [string]$MySqlExe,
    [string]$DbHost = '127.0.0.1',
    [int]$DbPort = 3306,
    [string]$DbUser = 'acore',
    [string]$AuthDatabase = 'acore_auth',
    [string]$WorldDatabase = 'acore_world',
    [string]$CharactersDatabase = 'acore_characters',
    [switch]$SkipSql
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-ExistingDirectory([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label does not exist: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Test-IsWithin([string]$Child, [string]$Parent) {
    return $Child.StartsWith($Parent.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
}

function Invoke-DbQuery([string]$Database, [string]$Sql) {
    $lines = @(& $MySqlExe "--host=$DbHost" "--port=$DbPort" "--user=$DbUser" `
        '--default-character-set=utf8mb4' '--batch' '--raw' '--skip-column-names' `
        "--database=$Database" "--execute=$Sql")
    if ($LASTEXITCODE -ne 0) { throw "MySQL query failed for database $Database" }
    return ,$lines
}

function Invoke-DbFile([string]$Database, [string]$Path) {
    $mysqlPath = ([IO.Path]::GetFullPath($Path)).Replace('\', '/')
    [void](Invoke-DbQuery $Database "source $mysqlPath")
}

$packageRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$manifestPath = Join-Path $packageRoot 'package-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Package manifest is missing: $manifestPath"
}
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
if ($manifest.package -ne 'mod-cultivation' -or $manifest.candidate -ne 'v2.0.0') {
    throw 'Unexpected package identity.'
}
foreach ($entry in $manifest.files) {
    $source = Join-Path $packageRoot $entry.path
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Package file is missing: $($entry.path)" }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
    if ($actual -ne $entry.sha256) { throw "Package hash mismatch: $($entry.path)" }
}

$ServerRoot = Resolve-ExistingDirectory $ServerRoot 'Server root'
$ClientRoot = Resolve-ExistingDirectory $ClientRoot 'Client root'
if (-not (Test-Path -LiteralPath (Join-Path $ServerRoot 'worldserver.exe') -PathType Leaf)) {
    throw 'The target server does not contain worldserver.exe.'
}
if (-not (Test-Path -LiteralPath (Join-Path $ClientRoot 'Wow-NWQ.exe') -PathType Leaf)) {
    throw 'The compatible target client must contain Wow-NWQ.exe.'
}
$clientHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $ClientRoot 'Wow-NWQ.exe')).Hash.ToLowerInvariant()
if ($clientHash -ne $manifest.compatibility.client_exe_sha256) {
    throw "Unsupported client executable. Expected build 12340 hash $($manifest.compatibility.client_exe_sha256), got $clientHash"
}
if (-not $ServerDataRoot) {
    $worldConfig = Join-Path $ServerRoot 'configs\worldserver.conf'
    $dataLine = @(Select-String -LiteralPath $worldConfig -Pattern '^\s*DataDir\s*=\s*"([^"]+)"')
    if ($dataLine.Count -ne 1) { throw 'Specify -ServerDataRoot: DataDir is ambiguous.' }
    $ServerDataRoot = $dataLine[0].Matches[0].Groups[1].Value
    if (-not [IO.Path]::IsPathRooted($ServerDataRoot)) { $ServerDataRoot = Join-Path $ServerRoot $ServerDataRoot }
}
$ServerDataRoot = Resolve-ExistingDirectory $ServerDataRoot 'Server DataDir'
foreach ($dll in $manifest.compatibility.runtime_dlls.PSObject.Properties) {
    $targetDll = Join-Path $ServerRoot $dll.Name
    if (-not (Test-Path -LiteralPath $targetDll) -or (Get-FileHash -LiteralPath $targetDll).Hash -ne $dll.Value) { throw "Incompatible runtime DLL: $($dll.Name)" }
}
$archives = @(Get-ChildItem -LiteralPath (Join-Path $ClientRoot 'Data') -Recurse -File -Filter '*.MPQ' | Where-Object Name -match '^patch(?:-ruru)?-[a-z]\.mpq$')
foreach ($archive in $archives) {
    $relative = $archive.FullName.Substring($ClientRoot.Length + 1).Replace('\','/')
    $baseline = $manifest.compatibility.client_inventory.PSObject.Properties[$relative]
    $replacement = @($manifest.files | Where-Object path -eq ('client/'+$relative))
    $actual = (Get-FileHash -LiteralPath $archive.FullName).Hash.ToLowerInvariant()
    if (-not $baseline -or ($actual -ne $baseline.Value -and ($replacement.Count -ne 1 -or $actual -ne $replacement[0].sha256))) { throw "Unsupported client patch chain: $relative" }
}
if ($archives.Count -ne @($manifest.compatibility.client_inventory.PSObject.Properties).Count) { throw 'Missing required client patch owner' }
foreach ($virtual in @('DBFilesClient\Spell.dbc','Interface\FrameXML\FrameXML.toc','Interface\FrameXML\CustomItemTooltips.lua')) {
    if (Test-Path -LiteralPath (Join-Path $ClientRoot $virtual)) { throw "Loose override: $virtual" }
}

if (-not (Test-Path -LiteralPath $BackupRoot -PathType Container)) { throw "Backup root is unavailable: $BackupRoot" }
$BackupRoot = (Resolve-Path -LiteralPath $BackupRoot).Path
if ((Test-IsWithin $BackupRoot $ServerRoot) -or (Test-IsWithin $BackupRoot $ClientRoot) -or
    (Test-IsWithin $ServerRoot $BackupRoot) -or (Test-IsWithin $ClientRoot $BackupRoot)) {
    throw 'Backup root must be outside both server and client roots.'
}

$running = @(Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -and ((Test-IsWithin $_.ExecutablePath $ServerRoot) -or (Test-IsWithin $_.ExecutablePath $ClientRoot))
})
if ($running.Count -gt 0) {
    throw ('Close the target client and server first: ' + (($running | ForEach-Object {$_.Name}) -join ', '))
}

$stamp = Get-Date -Format 'yyyyMMddTHHmmss'
$backup = Join-Path $BackupRoot "cultivation\pre-install-v2.0.0-$stamp"
if (Test-Path -LiteralPath $backup) { throw "Backup destination already exists: $backup" }
New-Item -ItemType Directory -Path $backup | Out-Null

$transfers = @(
    @{ Source='client\Data\ruRU\patch-ruRU-A.MPQ'; Target=(Join-Path $ClientRoot 'Data\ruRU\patch-ruRU-A.MPQ') },
    @{ Source='client\Data\ruRU\patch-ruRU-Z.MPQ'; Target=(Join-Path $ClientRoot 'Data\ruRU\patch-ruRU-Z.MPQ') },
    @{ Source='client\Data\ruRU\patch-ruRU-X.MPQ'; Target=(Join-Path $ClientRoot 'Data\ruRU\patch-ruRU-X.MPQ') },
    @{ Source='server\worldserver.exe'; Target=(Join-Path $ServerRoot 'worldserver.exe') }
)
if (-not (Test-Path -LiteralPath (Join-Path $ServerRoot 'configs\modules\mod_cultivation.conf'))) {
    $transfers += @{ Source='server\configs\modules\mod_cultivation.conf.dist'; Target=(Join-Path $ServerRoot 'configs\modules\mod_cultivation.conf') }
}
foreach ($name in @('Spell.dbc','SkillLineAbility.dbc','SpellDescriptionVariables.dbc','SpellIcon.dbc','SpellRadius.dbc','SpellRange.dbc')) {
    $transfers += @{ Source="server\data\dbc\$name"; Target=(Join-Path $ServerDataRoot "dbc\$name") }
}

$fileBackupRows = @()
foreach ($transfer in $transfers) {
    $source = Join-Path $packageRoot $transfer.Source
    $relativeBackup = 'files\' + $transfer.Source
    $backupFile = Join-Path $backup $relativeBackup
    $existed = Test-Path -LiteralPath $transfer.Target -PathType Leaf
    $beforeHash = $null
    if ($existed) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $backupFile) -Force | Out-Null
        Copy-Item -LiteralPath $transfer.Target -Destination $backupFile
        $beforeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $transfer.Target).Hash.ToLowerInvariant()
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $backupFile).Hash.ToLowerInvariant() -ne $beforeHash) {
            throw "Backup readback mismatch: $($transfer.Target)"
        }
    }
    $fileBackupRows += [pscustomobject]@{
        target = $transfer.Target
        backup = if ($existed) { $relativeBackup.Replace('\','/') } else { $null }
        existed = [bool]$existed
        before_sha256 = $beforeHash
        package_path = $transfer.Source.Replace('\','/')
        after_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
    }
}

$previousPassword = $env:MYSQL_PWD
$plainPassword = $null
$passwordPointer = [IntPtr]::Zero
try {
    $databaseBackups = @()
    if (-not $SkipSql) {
        if (-not $MySqlExe) { throw '-MySqlExe is required unless -SkipSql is used.' }
        $MySqlExe = (Resolve-Path -LiteralPath $MySqlExe).Path
        $dumpExe = Join-Path (Split-Path -Parent $MySqlExe) 'mysqldump.exe'
        if (-not (Test-Path -LiteralPath $dumpExe -PathType Leaf)) { throw "mysqldump.exe was not found: $dumpExe" }
        $securePassword = Read-Host 'MySQL password' -AsSecureString
        $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
        $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
        $env:MYSQL_PWD = $plainPassword

        if ((Invoke-DbQuery $CharactersDatabase 'SELECT COUNT(*) FROM characters WHERE online<>0;')[0] -ne '0') {
            throw 'Stop worldserver: characters.online contains active sessions.'
        }
        if ((Invoke-DbQuery $CharactersDatabase "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name IN ('character_rogue_path','character_rogue_path_suppressed_action');")[0] -ne '0') {
            throw 'Legacy mod-rogue-paths tables detected. Apply the schema-6 upgrade first.'
        }
        if ((Invoke-DbQuery $AuthDatabase "SELECT COUNT(*) FROM rbac_permissions WHERE id=1001 AND name<>'Command: cultivation';")[0] -ne '0') {
            throw 'RBAC permission 1001 is owned by another feature.'
        }
        if ((Invoke-DbQuery $WorldDatabase "SELECT COUNT(*) FROM creature_template WHERE entry=900406;")[0] -ne '0') {
            throw 'Creature template 900406 is already owned; use the versioned upgrade path instead of a fresh install.'
        }

        $dbBackupDir = Join-Path $backup 'databases'
        New-Item -ItemType Directory -Path $dbBackupDir | Out-Null
        foreach ($database in @($AuthDatabase,$WorldDatabase,$CharactersDatabase)) {
            $dumpPath = Join-Path $dbBackupDir ($database + '.sql')
            & $dumpExe "--host=$DbHost" "--port=$DbPort" "--user=$DbUser" '--single-transaction' '--no-tablespaces' `
                '--routines' '--triggers' '--databases' $database "--result-file=$dumpPath"
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $dumpPath) -or (Get-Item $dumpPath).Length -eq 0) {
                throw "Database backup failed: $database"
            }
            $databaseBackups += [pscustomobject]@{
                database = $database
                file = 'databases/' + $database + '.sql'
                bytes = (Get-Item -LiteralPath $dumpPath).Length
                sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $dumpPath).Hash.ToLowerInvariant()
            }
        }
    }

    $backupManifest = [ordered]@{
        status = 'verified-backup'
        package = 'mod-cultivation'
        candidate = 'v2.0.0'
        created = (Get-Date).ToString('o')
        files = $fileBackupRows
        databases = $databaseBackups
    }
    $backupManifestPath = Join-Path $backup 'backup-manifest.json'
    $backupManifest | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $backupManifestPath -Encoding utf8

    if (-not $SkipSql) {
        Invoke-DbFile $AuthDatabase (Join-Path $packageRoot 'sql\fresh\auth\cultivation_rbac.sql')
        Invoke-DbFile $CharactersDatabase (Join-Path $packageRoot 'sql\fresh\characters\character_cultivation_rogue.sql')
        Invoke-DbFile $WorldDatabase (Join-Path $packageRoot 'sql\fresh\world\cultivation_command.sql')
        Invoke-DbFile $WorldDatabase (Join-Path $packageRoot 'sql\fresh\world\cultivation_rogue_spells.sql')
        if ((Invoke-DbQuery $AuthDatabase "SELECT COUNT(*) FROM rbac_permissions WHERE id=1001 AND name='Command: cultivation';")[0] -ne '1') { throw 'Auth SQL postflight failed.' }
        if ((Invoke-DbQuery $WorldDatabase "SELECT COUNT(*) FROM command WHERE name='cultivation';")[0] -ne '1') { throw 'World SQL postflight failed.' }
        if ((Invoke-DbQuery $WorldDatabase "SELECT COUNT(*) FROM creature_template WHERE entry=900406 AND ScriptName='npc_cultivation_rogue_shadowstep_clone';")[0] -ne '1') { throw 'Shadowstep clone SQL postflight failed.' }
        if ((Invoke-DbQuery $WorldDatabase "SELECT COUNT(*) FROM creature_template_model WHERE CreatureID=900406;")[0] -eq '0') { throw 'Shadowstep clone model SQL postflight failed.' }
        if ((Invoke-DbQuery $CharactersDatabase "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name IN ('character_cultivation_rogue','character_cultivation_rogue_suppressed_action');")[0] -ne '2') { throw 'Characters SQL postflight failed.' }
    }

    foreach ($transfer in $transfers) {
        $source = Join-Path $packageRoot $transfer.Source
        New-Item -ItemType Directory -Path (Split-Path -Parent $transfer.Target) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $transfer.Target -Force
        $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
        $targetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $transfer.Target).Hash.ToLowerInvariant()
        if ($sourceHash -ne $targetHash) { throw "Installation readback mismatch: $($transfer.Target)" }
    }

    $backupManifest.status = 'installed-release-target-smoke-pending'
    $backupManifest | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $backupManifestPath -Encoding utf8
    Write-Host "Cultivation v2.0.0 installed. Launch Wow-NWQ.exe. Backup: $backup"
    Write-Host 'Verify .cultivation rogue status and perform GUI/gameplay acceptance.'
} finally {
    $env:MYSQL_PWD = $previousPassword
    $plainPassword = $null
    if ($passwordPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer) }
}
