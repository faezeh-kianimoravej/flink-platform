param(
    [string]$KafkaUserNamespace = "kafka-system",
    [string]$SecretName = "tenant-a-flink-user",
    [string]$BrokerNamespace = "kafka-system",
    [string]$BrokerPodName = "flink-platform-kafka-broker-0",
    [string]$RemoteOutputPath = "/tmp/tenant-a-client.properties"
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Decode-SecretValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($Value))
}

function Escape-JaasValue {
    param(
        [AllowNull()]
        [string]$Value
    )

    if ($null -eq $Value) {
        return ""
    }

    return $Value.Replace("\", "\\").Replace('"', '\"')
}

function Quote-ForSh {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return "'" + $Value.Replace("'", "'\''") + "'"
}

$secret = kubectl get secret $SecretName -n $KafkaUserNamespace -o json | ConvertFrom-Json

$username = $SecretName
if ($secret.data.PSObject.Properties.Name -contains "username") {
    $username = Decode-SecretValue $secret.data.username
} elseif ($secret.data.PSObject.Properties.Name -contains "sasl.username") {
    $username = Decode-SecretValue $secret.data."sasl.username"
}

if ($secret.data.PSObject.Properties.Name -contains "password") {
    $password = Decode-SecretValue $secret.data.password
} elseif ($secret.data.PSObject.Properties.Name -contains "sasl.password") {
    $password = Decode-SecretValue $secret.data."sasl.password"
} else {
    throw "Secret '$SecretName' in namespace '$KafkaUserNamespace' does not contain a password field."
}

$escapedUsername = Escape-JaasValue $username
$escapedPassword = Escape-JaasValue $password

$content = (@(
    "security.protocol=SASL_PLAINTEXT",
    "sasl.mechanism=SCRAM-SHA-512",
    "sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username=`"$escapedUsername`" password=`"$escapedPassword`";"
) -join [Environment]::NewLine) + [Environment]::NewLine

$quotedRemoteOutputPath = Quote-ForSh $RemoteOutputPath

$content | kubectl exec -i $BrokerPodName -n $BrokerNamespace -- sh -c "umask 077 && cat > $quotedRemoteOutputPath"
kubectl exec $BrokerPodName -n $BrokerNamespace -- sh -c "test -s $quotedRemoteOutputPath"

Write-Host "Created Kafka client properties inside pod:"
Write-Host "${BrokerNamespace}/${BrokerPodName}:${RemoteOutputPath}"
