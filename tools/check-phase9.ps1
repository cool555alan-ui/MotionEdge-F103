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
        'BSP\bsp_pwm.c', 'BSP\bsp_pwm.h',
        'Components\servo_actuator.c', 'Components\servo_actuator.h',
        'Services\actuator_service.c', 'Services\actuator_service.h',
        'host\motionctl\actuator_cli.py', 'host\tests\test_phase9.py',
        'docs\phase-09-actuator-control.md', 'docs\servo-pwm-calibration.md',
        'docs\actuator-safety-model.md')
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    Check 'Required files' ($missing.Count -eq 0) $(if ($missing) { $missing -join ', ' } else { 'all present' })

    $ioc = Get-Content -Raw -Encoding UTF8 'MotionEdge-F103.ioc'
    Check 'CubeMX TIM3_CH1' (($ioc -match 'PA6.Signal=S_TIM3_CH1') -and
        ($ioc -match 'TIM3.Prescaler=71') -and ($ioc -match 'TIM3.Period=19999')) `
        'PA6, PSC=71, ARR=19999'
    Check 'HAL timebase isolation' ($ioc -match 'NVIC.TimeBaseIP=TIM4') 'TIM4 remains HAL timebase'

    $service = Get-Content -Raw -Encoding UTF8 'Services\actuator_service.c'
    Check 'Default disabled' ($service -match 's_mode\s*=\s*ACTUATOR_MODE_DISABLED') 'PWM is not started by init'
    Check 'Explicit arm and owner' (($service -match 'ActuatorService_Arm') -and
        ($service -match 'ACTUATOR_RESULT_OWNER_CONFLICT')) 'single owner enforced'
    Check 'Safety mechanisms' (($service -match 'ACTUATOR_COMMAND_TIMEOUT_MS') -and
        ($service -match 'ActuatorService_EmergencyStop') -and ($service -match 'EnterFault')) `
        'timeout, ESTOP and fault interlock present'
    Check 'No new control task' (-not ((Get-Content -Raw -Encoding UTF8 'App\RTOS\rtos_tasks.c') -match 'ControlTask')) `
        '100 Hz SensorTask path reused'
    Check 'No Phase 9B PID' (-not (Test-Path 'Algorithms\pid_controller.c')) 'PID remains gated by real mechanics'

    $python = Get-Content -Raw -Encoding UTF8 'host\motionctl\mqtt_models.py'
    Check 'MQTT whitelist' (($python -match 'actuator_estop') -and ($python -match 'actuator_set_target')) `
        'manual actuator commands only'
    $gateway = Get-Content -Raw -Encoding UTF8 'host\motionctl\gateway.py'
    Check 'No side-effect retry' ($gateway -match 'retry=request.command not in SIDE_EFFECT_COMMANDS') `
        'actuator side effects are single-attempt'
    $flow = Get-Content -Raw -Encoding UTF8 'node-red\flows\motionedge-phase07.json'
    Check 'Node-RED manual controls' (($flow -match 'actuator_arm') -and
        ($flow -match 'actuator_estop') -and -not ($flow -match 'pid_enable')) `
        'no PID button'

    if ($failures) { exit 1 }
    Write-Host '[PASS] Phase 9A static safety checks complete'
}
finally { Pop-Location }
