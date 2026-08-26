[CmdletBinding(PositionalBinding = $true)]
param(
    [string]$Command,

    [string]$Value,

    [string]$RepoRoot = ".",
    [string]$Database,
    [switch]$Terms,
    [string]$Limit = "0",
    [string]$Hops = "2",
    [string]$Sqlite = "sqlite3.exe"
)

$ErrorActionPreference = "Stop"
trap {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 2
}
if ($Command -notin @("search", "traverse")) {
    throw "repo docs query error: command must be search or traverse"
}
if ([string]::IsNullOrWhiteSpace($Value)) {
    throw "repo docs query error: value must contain a non-whitespace character"
}
[int]$limitValue = 0
[int]$hopsValue = 0
if (-not [int]::TryParse($Limit, [ref]$limitValue)) {
    throw "repo docs query error: limit must be an integer"
}
if (-not [int]::TryParse($Hops, [ref]$hopsValue)) {
    throw "repo docs query error: hops must be an integer"
}

if ($Command -eq "search") {
    if ($limitValue -eq 0) { $limitValue = 10 }
    if ($limitValue -lt 1 -or $limitValue -gt 100) {
        throw "repo docs query error: limit must be between 1 and 100"
    }
    $mode = if ($Terms) { "terms" } else { "literal" }
    $sqlPath = Join-Path $PSScriptRoot "repo_docs_search.sql"
} else {
    if ($Terms) {
        throw "repo docs query error: -Terms is valid only for search"
    }
    if ($limitValue -eq 0) { $limitValue = 12 }
    if ($limitValue -lt 1 -or $limitValue -gt 12) {
        throw "repo docs query error: limit must be between 1 and 12"
    }
    if ($hopsValue -lt 1 -or $hopsValue -gt 2) {
        throw "repo docs query error: hops must be between 1 and 2"
    }
    $mode = "literal"
    $sqlPath = Join-Path $PSScriptRoot "repo_docs_traverse.sql"
}

$repoPath = (Resolve-Path -LiteralPath $RepoRoot).Path
if ([string]::IsNullOrWhiteSpace($Database)) {
    $databasePath = Join-Path $repoPath "state/repo_docs_index.sqlite"
} elseif ([IO.Path]::IsPathRooted($Database)) {
    $databasePath = $Database
} else {
    $databasePath = Join-Path $repoPath $Database
}
$databasePath = [IO.Path]::GetFullPath($databasePath)
if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) {
    throw "repo docs query error: derived index is missing; run rebuild"
}

$sqliteCommand = Get-Command $Sqlite -CommandType Application -ErrorAction SilentlyContinue
if ($null -eq $sqliteCommand) {
    throw "repo docs query error: sqlite3.exe is required for the native fast path"
}

$schemaVersion = & $sqliteCommand.Source -readonly $databasePath "SELECT value FROM index_metadata WHERE key = 'schema_version';" | Out-String
if ($LASTEXITCODE -ne 0) {
    throw "repo docs query error: derived index is malformed; run rebuild"
}
if ($schemaVersion.Trim() -ne "repo-docs-heading-index-v3") {
    throw "repo docs query error: derived index schema is incompatible; run rebuild"
}

$escaped = $Value.Replace("\", "\\").Replace('"', '\"')
if ($Command -eq "search") {
    $parameters = @(
        ".parameter set :query `"$escaped`"",
        ".parameter set :mode $mode",
        ".parameter set :limit $limitValue"
    )
} else {
    $parameters = @(
        ".parameter set :start `"$escaped`"",
        ".parameter set :hops $hopsValue",
        ".parameter set :limit $limitValue"
    )
}

$utf8 = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$sqlPathForSqlite = $sqlPath.Replace("\", "/")

$output = & $sqliteCommand.Source -readonly $databasePath ".parameter init" @parameters ".read `"$sqlPathForSqlite`"" | Out-String
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("repo docs query error: native SQLite query failed")
    exit 2
}
$output = $output.TrimEnd()
Write-Output $output
$payload = $output | ConvertFrom-Json
if ($null -ne $payload.error) {
    exit 2
}
