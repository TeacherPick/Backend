param(
    [switch]$Test,
    [string]$ConfigurationPath = (Join-Path $PSScriptRoot '..\.local\mysql\app.env')
)

if (!(Test-Path -LiteralPath $ConfigurationPath -PathType Leaf)) {
    throw '로컬 MySQL 설정이 없습니다. README의 MySQL 절차를 참고하세요.'
}

foreach ($setting in Get-Content -LiteralPath $ConfigurationPath) {
    if ($setting -match '^(DB_HOST|DB_PORT|DB_NAME|DB_USER|DB_PASSWORD)=(.*)$') {
        Set-Item -LiteralPath "Env:$($Matches[1])" -Value $Matches[2]
    }
}
if ($Test) { $env:DB_NAME = 'teacherpick_test' }
