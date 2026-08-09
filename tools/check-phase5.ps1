[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:Failures = 0

function Add-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    if ($Passed) {
        Write-Host "[PASS] $Name - $Detail" -ForegroundColor Green
    }
    else {
        ++$script:Failures
        Write-Host "[FAIL] $Name - $Detail" -ForegroundColor Red
    }
}

Push-Location $ProjectRoot
try {
    $required = @(
        'App\RTOS\app_rtos.c', 'App\RTOS\app_rtos.h',
        'App\RTOS\rtos_tasks.c', 'App\RTOS\rtos_tasks.h',
        'App\RTOS\rtos_objects.c', 'App\RTOS\rtos_objects.h',
        'App\RTOS\rtos_monitor.c', 'App\RTOS\rtos_monitor.h',
        'Inc\FreeRTOSConfig.h', 'Src\freertos.c',
        'Src\stm32f1xx_hal_timebase_tim.c'
    )
    $missing = @($required | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $ProjectRoot $_) -PathType Leaf)
        })
    Add-Check 'Required files' ($missing.Count -eq 0) `
        $(if ($missing) { $missing -join ', ' } else { 'all present' })

    $ioc = Get-Content -Raw -Encoding UTF8 'MotionEdge-F103.ioc'
    Add-Check 'CubeMX FreeRTOS' `
        (($ioc -match 'Mcu\.IP\d+=FREERTOS') -and
         ($ioc -match 'VP_FREERTOS_VS_CMSIS_V2\.Mode=CMSIS_V2')) `
        'CubeMX CMSIS-RTOS2 configuration'
    Add-Check 'HAL time base separated' `
        (($ioc -match 'NVIC\.TimeBaseIP=TIM4') -and
         (Test-Path -LiteralPath 'Src\stm32f1xx_hal_timebase_tim.c')) `
        'TIM4 provides HAL tick; SysTick remains for FreeRTOS'

    $tasks = Get-Content -Raw -Encoding UTF8 'App\RTOS\rtos_tasks.c'
    $taskHeader = Get-Content -Raw -Encoding UTF8 'App\RTOS\rtos_tasks.h'
    $allTasks = @('SensorTask', 'CommunicationTask', 'TelemetryTask', 'HealthTask') |
        ForEach-Object { $tasks -match ('\.name\s*=\s*"' + $_ + '"') }
    Add-Check 'Four application tasks' `
        (@($allTasks | Where-Object { -not $_ }).Count -eq 0) `
        'Sensor, Communication, Telemetry and Health'
    Add-Check 'Absolute periodic scheduling' `
        (($tasks -match 'SensorTask[\s\S]*osDelayUntil') -and
         ($tasks -match 'expected\s*\+=\s*RTOS_SENSOR_PERIOD_MS')) `
        'SensorTask uses osDelayUntil'
    Add-Check 'Task stacks explicit' `
        (($taskHeader -match 'RTOS_SENSOR_STACK_BYTES\s+1280U') -and
         ($taskHeader -match 'RTOS_COMMUNICATION_STACK_BYTES\s+1024U') -and
         ($taskHeader -match 'RTOS_TELEMETRY_STACK_BYTES\s+1088U') -and
         ($taskHeader -match 'RTOS_HEALTH_STACK_BYTES\s+1280U')) `
        '1280/1024/1088/1280 bytes from measured high-water marks'

    $main = Get-Content -Raw -Encoding UTF8 'Src\main.c'
    Add-Check 'RTOS owns main path' `
        (($main -match 'osKernelStart\s*\(') -and
         -not ($main -match 'App_RunOnce\s*\(\s*HAL_GetTick')) `
        'bare-metal entry retained but not called by main'

    $portableFiles = @(Get-ChildItem Algorithms,Common,Devices,Middleware,Services `
            -Recurse -File | Where-Object { $_.Extension -in '.c', '.h' })
    $rtosLeaks = @($portableFiles | Select-String -Pattern `
            '(?:cmsis_os2\.h|FreeRTOS\.h|task\.h)')
    Add-Check 'Portable modules remain RTOS-free' ($rtosLeaks.Count -eq 0) `
        'algorithms, drivers, protocol and services'

    $applicationFiles = @(Get-ChildItem App,BSP,Common,Devices,Middleware,Services `
            -Recurse -File | Where-Object { $_.Extension -in '.c', '.h' })
    $dynamic = @($applicationFiles | Select-String -Pattern `
            '\b(?:malloc|calloc|realloc|pvPortMalloc)\s*\(')
    Add-Check 'No application dynamic allocation' ($dynamic.Count -eq 0) `
        'no general heap calls in application modules'
    $delay = @($applicationFiles | Select-String -Pattern '\bHAL_Delay\s*\(')
    Add-Check 'No HAL_Delay' ($delay.Count -eq 0) 'application modules'

    $objects = (Get-Content -Raw -Encoding UTF8 'App\RTOS\rtos_objects.c') +
        (Get-Content -Raw -Encoding UTF8 'App\RTOS\rtos_objects.h')
    Add-Check 'Motion snapshot synchronized' `
        (($objects -match 's_motion_mutex') -and
         ($objects -match 'RtosObjects_PublishMotion') -and
         ($objects -match 'RtosObjects_GetMotionSnapshot')) `
        'single-writer snapshot protected by mutex'
    Add-Check 'UART serialized' `
        (($objects -match 's_uart_mutex') -and
         ($objects -match 'RTOS_UART_LOCK_TIMEOUT_MS')) `
        'finite mutex wait'
    $logger = (Get-Content -Raw -Encoding UTF8 'Middleware\logger.c') +
        (Get-Content -Raw -Encoding UTF8 'App\RTOS\app_rtos.c')
    Add-Check 'Logger formatting synchronized' `
        (($objects -match 's_logger_mutex') -and
         ($logger -match 'Logger_SetLock') -and
         ($logger -match 'Logger_WriteUnlocked')) `
        'shared static formatting buffers protected before use'
    $configuration = (Get-Content -Raw -Encoding UTF8 'Services\config_service.c') +
        (Get-Content -Raw -Encoding UTF8 'App\RTOS\app_rtos.c')
    Add-Check 'Runtime config snapshot synchronized' `
        (($configuration -match 'ConfigService_SetCriticalSection') -and
         ($configuration -match 'RtosObjects_EnterCritical')) `
        'short critical section protects multi-field copy'
    Add-Check 'Fixed command queue' `
        (($objects -match 'RTOS_COMMAND_QUEUE_CAPACITY\s+8U') -and
         ($objects -match 's_command_queue_storage')) `
        'capacity 8 with static storage'
    Add-Check 'Static object control blocks' `
        (($objects -match 'StaticSemaphore_t') -and
         ($objects -match 'StaticQueue_t') -and
         ($objects -match 'StaticEventGroup_t')) `
        'CMSIS attributes point to caller-owned memory'

    $monitor = (Get-Content -Raw -Encoding UTF8 'App\RTOS\rtos_monitor.c') +
        (Get-Content -Raw -Encoding UTF8 'App\RTOS\rtos_monitor.h') + $tasks
    Add-Check 'Stack high-water monitoring' `
        (($monitor -match 'uxTaskGetStackHighWaterMark') -and
         ($monitor -match 'stack_high_water_mark')) 'all four tasks'
    Add-Check 'Task liveness monitoring' `
        (($monitor -match 'RtosMonitor_AllCriticalTasksAlive') -and
         ($monitor -match 'last_heartbeat_ms')) 'watchdog-ready API'
    Add-Check 'Heap diagnostics' `
        (($monitor -match 'xPortGetFreeHeapSize') -and
         ($monitor -match 'xPortGetMinimumEverFreeHeapSize')) 'current and minimum heap'

    $config = Get-Content -Raw -Encoding UTF8 'Inc\FreeRTOSConfig.h'
    Add-Check 'RTOS baseline preserved' `
        (($config -match 'configTOTAL_HEAP_SIZE\s+\(\(size_t\)3072\)') -and
         ($config -match 'configUSE_TIMERS\s+1') -and
         ($config -match 'configTIMER_TASK_STACK_DEPTH\s+256')) `
        '3072-byte heap and timer task remain enabled'

    $trackedBuild = @(& git -C $ProjectRoot ls-files |
            Where-Object { $_ -match '^(?:build|build-host)/' })
    Add-Check 'Build outputs untracked' ($trackedBuild.Count -eq 0) `
        'no generated build output in Git'
    $readme = Get-Content -Raw -Encoding UTF8 'README.md'
    Add-Check 'No false RTOS hardware claim' `
        (-not ($readme -match 'FreeRTOS.{0,20}(?:实机|硬件).{0,20}(?:通过|完成)')) `
        'hardware status remains pending until capture passes'
}
finally {
    Pop-Location
}

if ($script:Failures -ne 0) {
    Write-Host "Phase 5 checks failed: $script:Failures" -ForegroundColor Red
    exit 1
}
Write-Host 'Phase 5 checks passed.' -ForegroundColor Green
exit 0
