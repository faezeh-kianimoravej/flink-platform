param(
    [string]$SourceNamespace = "kafka-system",
    [int]$TimeoutSeconds = 120,
    [int]$PollSeconds = 5
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$syncScript = Join-Path $PSScriptRoot "sync-kafka-user-secret.ps1"

& $syncScript `
    -Tenant "tenant-a" `
    -SourceNamespace $SourceNamespace `
    -DestinationNamespace "tenant-a" `
    -SecretName "tenant-a-flink-user" `
    -TimeoutSeconds $TimeoutSeconds `
    -PollSeconds $PollSeconds

& $syncScript `
    -Tenant "tenant-b" `
    -SourceNamespace $SourceNamespace `
    -DestinationNamespace "tenant-b" `
    -SecretName "tenant-b-flink-user" `
    -TimeoutSeconds $TimeoutSeconds `
    -PollSeconds $PollSeconds
