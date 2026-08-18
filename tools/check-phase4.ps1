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
        'Middleware\crc16.c',
        'Middleware\byte_ring_buffer.c',
        'Middleware\protocol_frame.c',
        'Middleware\protocol_parser.c',
        'Services\command_service.c',
        'Services\config_service.c',
        'Services\telemetry_service.c',
        'Services\communication_service.c',
        'Tests\Fixtures\protocol_vectors.json',
        'host\motionctl\protocol.py',
        'host\motionctl\device.py',
        'host\motionctl\cli.py',
        'docs\protocol-specification.md',
        'docs\phase-04-device-protocol.md'
    )
    $missing = @($required | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $ProjectRoot $_) -PathType Leaf)
        })
    Add-Check 'Required files' ($missing.Count -eq 0) `
        $(if ($missing) { $missing -join ', ' } else { 'all present' })

    $version = Get-Content -Raw -Encoding UTF8 `
        (Join-Path $ProjectRoot 'App\app_version.h')
    Add-Check 'Version includes Phase 4' `
        ($version -match 'APP_VERSION_STRING\s+"(?:0\.(?:4\.[1-9]|[5-9]\.[0-9]+)|[1-9][0-9]*\.[0-9]+\.[0-9]+)"') `
        'firmware version is 0.4.1 or later'

    $constants = Get-Content -Raw -Encoding UTF8 `
        (Join-Path $ProjectRoot 'Middleware\protocol_constants.h')
    Add-Check 'Protocol limits' `
        (($constants -match 'PROTOCOL_VERSION\s+0x01U') -and
         ($constants -match 'PROTOCOL_MAX_PAYLOAD_SIZE\s+128U')) `
        'v1 and 128-byte payload'

    $crc = (Get-Content -Raw -Encoding UTF8 `
            (Join-Path $ProjectRoot 'Middleware\crc16.c')) +
        (Get-Content -Raw -Encoding UTF8 `
            (Join-Path $ProjectRoot 'Middleware\crc16.h'))
    Add-Check 'CRC parameters' `
        (($crc -match '0x1021U') -and ($crc -match '0xFFFFU')) `
        'CCITT-FALSE polynomial and initial value'

    $coreFiles = @(
        'Middleware\crc16.c', 'Middleware\crc16.h',
        'Middleware\byte_ring_buffer.c', 'Middleware\byte_ring_buffer.h',
        'Middleware\protocol_frame.c', 'Middleware\protocol_frame.h',
        'Middleware\protocol_parser.c', 'Middleware\protocol_parser.h',
        'Middleware\protocol_constants.h'
    ) | ForEach-Object { Get-Item -LiteralPath (Join-Path $ProjectRoot $_) }
    $hal = @($coreFiles | Select-String -Pattern '(?i)HAL_|stm32|main\.h|usart\.h')
    Add-Check 'Protocol core portable' ($hal.Count -eq 0) 'no HAL dependency'

    $userFiles = @(Get-ChildItem -LiteralPath `
            @('Algorithms', 'App', 'BSP', 'Common', 'Devices', 'Middleware', 'Services') `
            -Recurse -File | Where-Object { $_.Extension -in '.c', '.h' })
    $dynamic = @($userFiles |
            Select-String -Pattern '\b(?:malloc|calloc|realloc)\s*\(')
    Add-Check 'No dynamic memory' ($dynamic.Count -eq 0) 'user C modules'
    $delay = @($userFiles | Select-String -Pattern '\bHAL_Delay\s*\(')
    Add-Check 'No HAL_Delay' ($delay.Count -eq 0) 'user C modules'

    $frame = Get-Content -Raw -Encoding UTF8 `
        (Join-Path $ProjectRoot 'Middleware\protocol_frame.c')
    Add-Check 'Payload boundary guarded' `
        ($frame -match 'PROTOCOL_MAX_PAYLOAD_SIZE') 'encode/decode checks'

    $config = Get-Content -Raw -Encoding UTF8 `
        (Join-Path $ProjectRoot 'Services\config_service.c')
    Add-Check 'Configuration fully validated' `
        (($config -match 'static bool IsValid') -and
         ($config.IndexOf('IsValid(config)') -lt $config.IndexOf('SensorService_SetSamplePeriod'))) `
        'validation precedes service updates'

    $parserTest = Get-Content -Raw -Encoding UTF8 `
        (Join-Path $ProjectRoot 'Tests\Host\test_protocol.c')
    Add-Check 'Parser recovery tested' `
        (($parserTest -match 'crc_errors') -and
         ($parserTest -match 'PROTOCOL_PARSE_LENGTH_ERROR') -and
         ($parserTest -match 'successful_frames')) 'CRC and length recovery'

    $uart = Get-Content -Raw -Encoding UTF8 (Join-Path $ProjectRoot 'BSP\bsp_uart.c')
    $uartIrq = Get-Content -Raw -Encoding UTF8 `
        (Join-Path $ProjectRoot 'Src\stm32f1xx_it.c')
    # 固定缓冲区的中断或循环DMA接收都属于有界实现。
    $singleByteReceive = [bool]($uart -match 'HAL_UART_Receive_IT\(&huart1,\s*&s_rx_byte,\s*1U\)')
    $chunkedIdleReceive = [bool](($uart -match 'HAL_UARTEx_ReceiveToIdle_IT\s*\(') -and ($uart -match 'BSP_UART_RX_CHUNK_SIZE'))
    $directRingReceive = [bool](($uart -match 'USART_SR_RXNE') -and ($uart -match 'PushRxByte\s*\('))
    $ioc = Get-Content -Raw -Encoding UTF8 (Join-Path $ProjectRoot 'MotionEdge-F103.ioc')
    $circularDmaReceive = [bool](($uart -match 'HAL_UART_Receive_DMA\s*\(') -and
        ($uart -match 'BSP_UART_RX_DMA_CAPACITY') -and
        ($ioc -match 'Dma\.USART1_RX\.0\.Mode=DMA_CIRCULAR'))
    $boundedReceive = [bool]($singleByteReceive -or $chunkedIdleReceive -or
        $directRingReceive -or $circularDmaReceive)
    $uartReceivePassed = ($boundedReceive -and
                          ($uart -match 'BSP_UART_RX_(?:DMA_)?CAPACITY') -and
                          ($uartIrq -match 'BspUart_IrqHandler\s*\('))
    Add-Check -Name 'UART receive bounded' -Passed $uartReceivePassed `
        -Detail 'fixed receive buffer with USART1 error handling'

    $app = Get-Content -Raw -Encoding UTF8 (Join-Path $ProjectRoot 'App\app_main.c')
    Add-Check 'Binary mode isolated' `
        (($app -match 'CommunicationService_IsProtocolMode') -and
         ($app -match '!CommunicationService_IsProtocolMode\(\)')) `
        'text and CSV guarded'

    $readme = Get-Content -Raw -Encoding UTF8 (Join-Path $ProjectRoot 'README.md')
    $phaseDoc = Get-Content -Raw -Encoding UTF8 `
        (Join-Path $ProjectRoot 'docs\phase-04-device-protocol.md')
    Add-Check 'Hardware boundary documented' `
        (($readme -match 'Phase 4: Binary Device Protocol') -and
         ($phaseDoc -match 'Phase 1.*hardware validation is complete') -and
         ($phaseDoc -match 'Binary protocol hardware') -and
         ($phaseDoc -match 'Breadboard validation')) `
        'Phase 1-3 hardware passed; binary protocol remains pending'

    $trackedBuild = @(& git -C $ProjectRoot ls-files |
            Where-Object { $_ -match '^(?:build|build-host)/' })
    Add-Check 'Build outputs untracked' ($trackedBuild.Count -eq 0) `
        'no generated outputs'

    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $null = & git -C $ProjectRoot diff --check 2>$null
    $diffPassed = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $savedPreference
    Add-Check 'Git diff format' $diffPassed 'no whitespace errors'
}
finally {
    Pop-Location
}

if ($script:Failures -ne 0) {
    Write-Host "Phase 4 checks failed: $script:Failures" -ForegroundColor Red
    exit 1
}
Write-Host 'Phase 4 checks passed.' -ForegroundColor Green
exit 0
