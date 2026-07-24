#include "crc16.h"

#include <stddef.h>

uint16_t Crc16CcittFalse_Update(uint16_t current_crc,
                               const uint8_t *data,
                               size_t length)
{
    size_t index;
    uint8_t bit;

    if ((data == NULL) && (length != 0U))
    {
        return current_crc;
    }
    for (index = 0U; index < length; ++index)
    {
        current_crc ^= (uint16_t)data[index] << 8U;
        for (bit = 0U; bit < 8U; ++bit)
        {
            current_crc = ((current_crc & 0x8000U) != 0U)
                              ? (uint16_t)((current_crc << 1U) ^
                                           CRC16_CCITT_FALSE_POLYNOMIAL)
                              : (uint16_t)(current_crc << 1U);
        }
    }
    return current_crc;
}

uint16_t Crc16CcittFalse_Calculate(const uint8_t *data, size_t length)
{
    return Crc16CcittFalse_Update(CRC16_CCITT_FALSE_INITIAL, data, length);
}
