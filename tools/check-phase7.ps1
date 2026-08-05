[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$required=@(
  'host\motionctl\gateway.py','host\motionctl\gateway_cli.py','host\motionctl\gateway_config.py',
  'host\motionctl\mqtt_client.py','host\motionctl\mqtt_models.py','host\motionctl\mqtt_topics.py',
  'config\motionedge-gateway.example.toml','node-red\flows\motionedge-phase07.json',
  'docs\phase-07-mqtt-gateway.md','docs\mqtt-topic-contract.md',
  'docs\node-red-dashboard.md','docs\phase-07-validation-method.md')
foreach($relative in $required){if(-not(Test-Path (Join-Path $root $relative))){Write-Error "Missing Phase 7 file: $relative";exit 2}}
$gateway=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'host\motionctl\gateway.py')
$mqtt=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'host\motionctl\mqtt_client.py')
$topics=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'host\motionctl\mqtt_topics.py')
$protocol=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'host\motionctl\protocol.py')
$config=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'config\motionedge-gateway.example.toml')
$all=$gateway+$mqtt+$topics
if($protocol-match'paho|mqtt'){Write-Error 'Protocol layer depends on MQTT';exit 3}
foreach($needle in @('DeviceClient','queue.Queue','CommandResultCache','RETAINED_COMMAND_REJECTED','ReconnectBackoff','reconnect_delay_set','will_set')){if(-not$all.Contains($needle)){Write-Error "Missing gateway safety mechanism: $needle";exit 4}}
if($gateway-match'COM4'){Write-Error 'COM4 is hard-coded in gateway source';exit 5}
if($all-match'\b(pwm|pid)\b'){Write-Error 'Forbidden actuator command found';exit 6}
if($config-match'password\s*=\s*"[^"\r\n]+"'){Write-Error 'Plaintext MQTT password in example config';exit 7}
if(-not$topics.Contains('TopicRule(self.motion, qos_telemetry, False)')-or-not$topics.Contains('TopicRule(self.command, qos_command, False)')){Write-Error 'Telemetry or command retain rule invalid';exit 8}
if(-not$topics.Contains('TopicRule(self.state, qos_state, True)')){Write-Error 'State must be retained';exit 9}
& (Join-Path $root 'tools\validate-node-red-flow.ps1')
if($LASTEXITCODE-ne 0){exit $LASTEXITCODE}
$trackedLogs=@(git -C $root ls-files 'artifacts/phase07/*.log' 'artifacts/phase07/final-validation/mqtt-capture.jsonl')
if($trackedLogs.Count-gt 0){Write-Error 'Large Phase 7 logs are tracked';exit 10}
Write-Host '[PASS] Phase 7 static architecture, safety, Flow, documentation and artifact checks'
