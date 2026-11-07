param([ValidateSet('install','dev','build','test')][string]$Task='dev')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$frontendPath=Join-Path $projectRoot 'frontend'
Push-Location $frontendPath
try {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        if ($Task -eq 'install') { npm install } else { npm run $Task }
    } else {
        $bundledPnpm=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\pnpm\dist\pnpm.mjs'
        if (!(Test-Path -LiteralPath $bundledPnpm)) { throw 'Install Node.js with npm, or use pnpm.' }
        if ($Task -eq 'install') { node $bundledPnpm install } else { node $bundledPnpm run $Task }
    }
} finally { Pop-Location }
