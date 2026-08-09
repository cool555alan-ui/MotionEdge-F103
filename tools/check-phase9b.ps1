[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$failures = 0

function Check([string]$name, [bool]$ok, [string]$detail) {
    if ($ok) { Write-Host "[PASS] $name - $detail" -ForegroundColor Green }
    else { Write-Host "[FAIL] $name - $detail" -ForegroundColor Red; $script:failures++ }
}

Push-Location $root
try {
    $required = @(
        'Algorithms\pid_controller.c', 'Algorithms\pid_controller.h',
        'Services\control_service.c', 'Services\control_service.h',
        'host\motionctl\control_cli.py', 'host\motionctl\control_experiment.py',
        'host\tests\test_phase9b.py', 'docs\pid-attitude-control.md')
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    Check 'Required files' ($missing.Count -eq 0) $(if ($missing) { $missing -join ', ' } else { 'all present' })

    $pidSource = Get-Content -Raw -Encoding UTF8 'Algorithms\pid_controller.c'
    $control = Get-Content -Raw -Encoding UTF8 'Services\control_service.c'
    $tasks = Get-Content -Raw -Encoding UTF8 'App\RTOS\rtos_tasks.c'
    $actuator = Get-Content -Raw -Encoding UTF8 'Services\actuator_service.c'
    $gateway = Get-Content -Raw -Encoding UTF8 'host\motionctl\gateway.py'
    $mqtt = Get-Content -Raw -Encoding UTF8 'host\motionctl\mqtt_models.py'
    $flow = Get-Content -Raw -Encoding UTF8 'node-red\flows\motionedge-phase07.json'
    $readme = Get-Content -Raw -Encoding UTF8 'README.md'

    Check 'PID portable' (-not ($pidSource -match 'stm32|HAL_|FreeRTOS|cmsis_os|TIM3|mqtt')) 'no HAL, RTOS, PWM or MQTT dependency'
    Check 'Control has no TIM/HAL' (-not ($control -match 'HAL_|TIM3|htim')) 'uses ActuatorService only'
    Check 'No ControlTask' (-not ($tasks -match 'ControlTask|s_control_task')) 'SensorTask 100 Hz path reused'
    Check 'No dynamic memory' (-not (($pidSource + $control) -match '\b(malloc|calloc|realloc|free)\s*\(')) 'fixed static storage'
    Check 'PWM window unchanged' ($actuator -match '1450U, 1500U, 1550U') '1450..1550 us'
    Check 'PID routed through actuator' ($control -match 'ActuatorService_SetControlPulse') 'no direct CCR write'
    Check 'Sensor and stale interlock' (($control -match 'CONTROL_FAULT_SENSOR_OFFLINE') -and
        ($control -match 'CONTROL_FAULT_STALE_MOTION')) 'both force safe state'
    Check 'ESTOP and App Fault interlock' (($control -match 'ActuatorService_EmergencyStop') -and
        ($control -match 'CONTROL_FAULT_APP_FAULT')) 'highest-priority safety path'
    Check 'MQTT not real-time loop' (-not ($control -match '#include\s+[<"](mqtt|gateway)')) 'MQTT remains outside firmware controller'
    Check 'MQTT command safety' (($mqtt -match 'control_enable') -and
        ($gateway -match 'retry=request.command not in SIDE_EFFECT_COMMANDS')) 'retained/duplicate framework and no retry retained'
    Check 'Node-RED honest naming' (-not ($flow -match '(?i)closed[ -]?loop')) 'PID Attitude Control only'
    Check 'README boundary' (($readme -match 'PID-based attitude-driven servo control') -and
        ($readme -match '100 Hz')) 'single-IMU interpretation and local rate explicit'
    Check 'Firmware version' ((Get-Content -Raw 'App\app_version.h') -match 'APP_VERSION_STRING "0\.9\.1"') '0.9.1'
    Check 'Python version' ((Get-Content -Raw 'host\motionctl\__init__.py') -match '__version__ = "0\.9\.1"') '0.9.1'

    git diff --check
    Check 'Git diff format' ($LASTEXITCODE -eq 0) 'no whitespace errors'
    if ($failures) { exit 1 }
    Write-Host '[PASS] Phase 9B PID attitude-driven control static checks complete'
}
finally { Pop-Location }
