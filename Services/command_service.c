#include "command_service.h"

#include <stddef.h>

#include "app_status.h"
#include "app_version.h"
#include "actuator_service.h"
#include "config_service.h"
#include "motion_service.h"
#include "telemetry_service.h"

static CommandServiceMode_t s_mode;

static uint16_t Get16(const uint8_t *data)
{
    return (uint16_t)data[0] | ((uint16_t)data[1] << 8U);
}

static void Put16(uint8_t *data, uint16_t value)
{
    data[0] = (uint8_t)value;
    data[1] = (uint8_t)(value >> 8U);
}

static bool BuildResponse(const ProtocolFrame_t *request,
                          ProtocolStatusCode_t status,
                          uint16_t detail,
                          const uint8_t *data,
                          uint16_t data_length,
                          ProtocolFrame_t *response)
{
    if ((request == NULL) || (response == NULL) ||
        (data_length > (PROTOCOL_MAX_PAYLOAD_SIZE - 6U)) ||
        ((data == NULL) && (data_length != 0U)))
    {
        return false;
    }
    *response = (ProtocolFrame_t){0};
    response->version = PROTOCOL_VERSION;
    response->type = PROTOCOL_TYPE_COMMAND_RESPONSE;
    response->sequence = request->sequence;
    response->payload[0] = request->type;
    response->payload[1] = (uint8_t)status;
    Put16(&response->payload[2], detail);
    Put16(&response->payload[4], data_length);
    if (data_length != 0U)
    {
        size_t index;
        for (index = 0U; index < data_length; ++index)
        {
            response->payload[6U + index] = data[index];
        }
    }
    response->payload_length = (uint16_t)(6U + data_length);
    return true;
}

static void SerializeConfig(const RuntimeConfig_t *config, uint8_t *data)
{
    Put16(&data[0], config->sensor_sample_period_ms);
    Put16(&data[2], config->telemetry_period_ms);
    Put16(&data[4], config->low_pass_alpha_milli);
    Put16(&data[6], config->complementary_gyro_weight_milli);
    data[8] = config->log_level;
    data[9] = config->telemetry_enabled ? 1U : 0U;
}

static void DeserializeConfig(const uint8_t *data, RuntimeConfig_t *config)
{
    config->sensor_sample_period_ms = Get16(&data[0]);
    config->telemetry_period_ms = Get16(&data[2]);
    config->low_pass_alpha_milli = Get16(&data[4]);
    config->complementary_gyro_weight_milli = Get16(&data[6]);
    config->log_level = data[8];
    config->telemetry_enabled = data[9] != 0U;
}

static ProtocolStatusCode_t ActuatorStatusToProtocol(ActuatorResult_t result)
{
    switch (result)
    {
        case ACTUATOR_RESULT_OK: return PROTOCOL_STATUS_OK;
        case ACTUATOR_RESULT_INVALID_ARGUMENT: return PROTOCOL_STATUS_INVALID_VALUE;
        case ACTUATOR_RESULT_NOT_ARMED: return PROTOCOL_STATUS_NOT_READY;
        case ACTUATOR_RESULT_OWNER_CONFLICT:
        case ACTUATOR_RESULT_FAULT: return PROTOCOL_STATUS_BUSY;
        case ACTUATOR_RESULT_UNSUPPORTED: return PROTOCOL_STATUS_UNSUPPORTED;
        case ACTUATOR_RESULT_HARDWARE:
        default: return PROTOCOL_STATUS_INTERNAL_ERROR;
    }
}

static bool IsProtocolOwner(uint8_t owner)
{
    return (owner == (uint8_t)ACTUATOR_OWNER_SERIAL) ||
           (owner == (uint8_t)ACTUATOR_OWNER_MQTT);
}

static bool BuildActuatorResult(const ProtocolFrame_t *request,
                                ActuatorResult_t result,
                                ProtocolFrame_t *response)
{
    return BuildResponse(request,
                         ActuatorStatusToProtocol(result),
                         (uint16_t)result,
                         NULL,
                         0U,
                         response);
}

bool CommandService_Init(void)
{
    s_mode = COMMAND_SERVICE_MODE_DEVELOPMENT;
    return ConfigService_Init();
}

bool CommandService_Process(const ProtocolFrame_t *request,
                            ProtocolFrame_t *response)
{
    RuntimeConfig_t config;
    uint8_t data[TELEMETRY_MOTION_PAYLOAD_SIZE];

    if ((request == NULL) || (response == NULL) ||
        (request->version != PROTOCOL_VERSION))
    {
        return false;
    }
    switch (request->type)
    {
        case PROTOCOL_TYPE_PING:
            if (request->payload_length != 0U)
            {
                return BuildResponse(request,
                                     PROTOCOL_STATUS_INVALID_LENGTH,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            return BuildResponse(
                request, PROTOCOL_STATUS_OK, 0U, NULL, 0U, response);
        case PROTOCOL_TYPE_GET_DEVICE_INFO:
            if (request->payload_length != 0U)
            {
                return BuildResponse(request,
                                     PROTOCOL_STATUS_INVALID_LENGTH,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            data[0] = APP_VERSION_MAJOR;
            data[1] = APP_VERSION_MINOR;
            data[2] = APP_VERSION_PATCH;
            data[3] = PROTOCOL_VERSION;
            return BuildResponse(
                request, PROTOCOL_STATUS_OK, 0U, data, 4U, response);
        case PROTOCOL_TYPE_GET_STATUS:
            if (request->payload_length != 0U)
            {
                return BuildResponse(request,
                                     PROTOCOL_STATUS_INVALID_LENGTH,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            data[0] = (uint8_t)AppStatus_GetState();
            data[1] = (uint8_t)MotionService_GetState();
            return BuildResponse(
                request, PROTOCOL_STATUS_OK, 0U, data, 2U, response);
        case PROTOCOL_TYPE_GET_CONFIG:
            if ((request->payload_length != 0U) || !ConfigService_Get(&config))
            {
                return BuildResponse(request,
                                     request->payload_length != 0U
                                         ? PROTOCOL_STATUS_INVALID_LENGTH
                                         : PROTOCOL_STATUS_INTERNAL_ERROR,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            SerializeConfig(&config, data);
            return BuildResponse(
                request, PROTOCOL_STATUS_OK, 0U, data, 10U, response);
        case PROTOCOL_TYPE_SET_CONFIG:
            if (request->payload_length != 10U)
            {
                return BuildResponse(request,
                                     PROTOCOL_STATUS_INVALID_LENGTH,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            DeserializeConfig(request->payload, &config);
            if (!ConfigService_Set(&config))
            {
                return BuildResponse(request,
                                     PROTOCOL_STATUS_INVALID_VALUE,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            s_mode = config.telemetry_enabled
                         ? COMMAND_SERVICE_MODE_PROTOCOL
                         : COMMAND_SERVICE_MODE_DEVELOPMENT;
            return BuildResponse(
                request, PROTOCOL_STATUS_OK, 0U, NULL, 0U, response);
        case PROTOCOL_TYPE_START_CALIBRATION:
            if (request->payload_length != 0U)
            {
                return BuildResponse(request,
                                     PROTOCOL_STATUS_INVALID_LENGTH,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            return BuildResponse(request,
                                 MotionService_StartCalibration()
                                     ? PROTOCOL_STATUS_OK
                                     : PROTOCOL_STATUS_BUSY,
                                 0U,
                                 NULL,
                                 0U,
                                 response);
        case PROTOCOL_TYPE_SET_STREAM_STATE:
            if ((request->payload_length != 1U) || (request->payload[0] > 1U) ||
                !ConfigService_Get(&config))
            {
                return BuildResponse(request,
                                     request->payload_length != 1U
                                         ? PROTOCOL_STATUS_INVALID_LENGTH
                                         : PROTOCOL_STATUS_INVALID_VALUE,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            config.telemetry_enabled = request->payload[0] != 0U;
            if (!ConfigService_Set(&config))
            {
                return BuildResponse(request,
                                     PROTOCOL_STATUS_INTERNAL_ERROR,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            s_mode = config.telemetry_enabled
                         ? COMMAND_SERVICE_MODE_PROTOCOL
                         : COMMAND_SERVICE_MODE_DEVELOPMENT;
            return BuildResponse(
                request, PROTOCOL_STATUS_OK, 0U, NULL, 0U, response);
        case PROTOCOL_TYPE_GET_LATEST_MOTION:
        {
            MotionFrame_t motion;
            ProtocolFrame_t telemetry;
            if (request->payload_length != 0U)
            {
                return BuildResponse(request,
                                     PROTOCOL_STATUS_INVALID_LENGTH,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            if (!MotionService_GetLatestFrame(&motion) ||
                !TelemetryService_BuildMotion(&motion, 0U, &telemetry))
            {
                return BuildResponse(request,
                                     PROTOCOL_STATUS_NOT_READY,
                                     0U,
                                     NULL,
                                     0U,
                                     response);
            }
            return BuildResponse(request,
                                 PROTOCOL_STATUS_OK,
                                 0U,
                                 telemetry.payload,
                                 telemetry.payload_length,
                                 response);
        }
        case PROTOCOL_TYPE_ACTUATOR_GET_STATUS:
        {
            ActuatorStatus_t status;
            ProtocolFrame_t telemetry;
            if (request->payload_length != 0U)
            {
                return BuildResponse(request, PROTOCOL_STATUS_INVALID_LENGTH,
                                     0U, NULL, 0U, response);
            }
            if (!ActuatorService_GetCurrentStatus(&status) ||
                !TelemetryService_BuildActuator(&status, 0U, &telemetry))
            {
                return BuildResponse(request, PROTOCOL_STATUS_NOT_READY,
                                     0U, NULL, 0U, response);
            }
            return BuildResponse(request, PROTOCOL_STATUS_OK, 0U,
                                 telemetry.payload, telemetry.payload_length,
                                 response);
        }
        case PROTOCOL_TYPE_ACTUATOR_ARM:
        case PROTOCOL_TYPE_ACTUATOR_DISARM:
        case PROTOCOL_TYPE_ACTUATOR_CENTER:
        case PROTOCOL_TYPE_ACTUATOR_ESTOP:
            if ((request->payload_length != 1U) ||
                !IsProtocolOwner(request->payload[0]))
            {
                return BuildResponse(request,
                                     request->payload_length != 1U
                                         ? PROTOCOL_STATUS_INVALID_LENGTH
                                         : PROTOCOL_STATUS_INVALID_VALUE,
                                     0U, NULL, 0U, response);
            }
            if (request->type == PROTOCOL_TYPE_ACTUATOR_ARM)
            {
                return BuildActuatorResult(
                    request,
                    ActuatorService_Arm((ActuatorOwner_t)request->payload[0]),
                    response);
            }
            if (request->type == PROTOCOL_TYPE_ACTUATOR_DISARM)
            {
                return BuildActuatorResult(
                    request,
                    ActuatorService_Disarm((ActuatorOwner_t)request->payload[0]),
                    response);
            }
            if (request->type == PROTOCOL_TYPE_ACTUATOR_CENTER)
            {
                return BuildActuatorResult(
                    request,
                    ActuatorService_Center((ActuatorOwner_t)request->payload[0]),
                    response);
            }
            return BuildActuatorResult(
                request,
                ActuatorService_EmergencyStop(
                    (ActuatorOwner_t)request->payload[0]),
                response);
        case PROTOCOL_TYPE_ACTUATOR_SET_TARGET:
        {
            int16_t angle;
            if ((request->payload_length != 3U) ||
                !IsProtocolOwner(request->payload[0]))
            {
                return BuildResponse(request,
                                     request->payload_length != 3U
                                         ? PROTOCOL_STATUS_INVALID_LENGTH
                                         : PROTOCOL_STATUS_INVALID_VALUE,
                                     0U, NULL, 0U, response);
            }
            angle = (int16_t)Get16(&request->payload[1]);
            if ((angle < -4500) || (angle > 4500))
            {
                return BuildResponse(request, PROTOCOL_STATUS_INVALID_VALUE,
                                     0U, NULL, 0U, response);
            }
            return BuildActuatorResult(
                request,
                ActuatorService_SetTargetAngle(
                    (ActuatorOwner_t)request->payload[0], angle),
                response);
        }
        case PROTOCOL_TYPE_ACTUATOR_SET_RAW_PULSE:
        {
            uint16_t pulse;
            if ((request->payload_length != 3U) ||
                !IsProtocolOwner(request->payload[0]))
            {
                return BuildResponse(request,
                                     request->payload_length != 3U
                                         ? PROTOCOL_STATUS_INVALID_LENGTH
                                         : PROTOCOL_STATUS_INVALID_VALUE,
                                     0U, NULL, 0U, response);
            }
            pulse = Get16(&request->payload[1]);
            if ((pulse < 1000U) || (pulse > 2000U))
            {
                return BuildResponse(request, PROTOCOL_STATUS_INVALID_VALUE,
                                     0U, NULL, 0U, response);
            }
            return BuildActuatorResult(
                request,
                ActuatorService_SetRawPulse(
                    (ActuatorOwner_t)request->payload[0], pulse),
                response);
        }
        default:
            return BuildResponse(request,
                                 PROTOCOL_STATUS_INVALID_COMMAND,
                                 0U,
                                 NULL,
                                 0U,
                                 response);
    }
}

bool CommandService_IsProtocolMode(void)
{
    return s_mode == COMMAND_SERVICE_MODE_PROTOCOL;
}

CommandServiceMode_t CommandService_GetMode(void)
{
    return s_mode;
}
