param(
    [string]$Tenant = "",
    [string]$SourceNamespace = "kafka-system",
    [string]$DestinationNamespace = "",
    [string]$SecretName = "",
    [int]$TimeoutSeconds = 120,
    [int]$PollSeconds = 5
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if ([string]::IsNullOrWhiteSpace($DestinationNamespace)) {
    if ([string]::IsNullOrWhiteSpace($Tenant)) {
        throw "Provide -DestinationNamespace or -Tenant."
    }

    $DestinationNamespace = $Tenant
}

if ([string]::IsNullOrWhiteSpace($SecretName)) {
    if ([string]::IsNullOrWhiteSpace($Tenant)) {
        throw "Provide -SecretName or -Tenant."
    }

    $SecretName = "$Tenant-flink-user"
}

if ($TimeoutSeconds -lt 1) {
    throw "-TimeoutSeconds must be greater than zero."
}

if ($PollSeconds -lt 1) {
    throw "-PollSeconds must be greater than zero."
}

function Get-SecretJsonWhenReady {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Namespace,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [int]$Timeout,
        [Parameter(Mandatory = $true)]
        [int]$PollInterval
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($Timeout)

    while ([DateTime]::UtcNow -le $deadline) {
        $json = kubectl get secret $Name -n $Namespace -o json 2>$null
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($json)) {
            return $json | ConvertFrom-Json
        }

        Start-Sleep -Seconds $PollInterval
    }

    throw "Timed out waiting for Secret '${Namespace}/${Name}'."
}

Write-Host "Waiting for source Secret ${SourceNamespace}/${SecretName}"
$sourceSecret = Get-SecretJsonWhenReady `
    -Namespace $SourceNamespace `
    -Name $SecretName `
    -Timeout $TimeoutSeconds `
    -PollInterval $PollSeconds

if ($null -eq $sourceSecret.data -or $sourceSecret.data.PSObject.Properties.Count -eq 0) {
    throw "Source Secret '${SourceNamespace}/${SecretName}' has no data."
}

$destinationSecret = [ordered]@{
    apiVersion = "v1"
    kind = "Secret"
    metadata = [ordered]@{
        name = $SecretName
        namespace = $DestinationNamespace
    }
    type = $sourceSecret.type
    data = $sourceSecret.data
}

Write-Host "Synchronizing Secret ${SourceNamespace}/${SecretName} to ${DestinationNamespace}/${SecretName}"
$destinationSecret |
    ConvertTo-Json -Depth 100 |
    kubectl apply --server-side --field-manager=flink-platform-secret-sync --force-conflicts -f -

if ($LASTEXITCODE -ne 0) {
    throw "Failed to synchronize Secret '${DestinationNamespace}/${SecretName}'."
}

$verifiedSecret = kubectl get secret $SecretName -n $DestinationNamespace -o name
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($verifiedSecret)) {
    throw "Destination Secret '${DestinationNamespace}/${SecretName}' was not found after synchronization."
}

Write-Host "Verified destination Secret ${DestinationNamespace}/${SecretName}"
