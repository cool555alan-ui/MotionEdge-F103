#ifndef CRC16_H
#define CRC16_H

#include <stddef.h>
#include <stdint.h>

#define CRC16_CCITT_FALSE_INITIAL 0xFFFFU
#define CRC16_CCITT_FALSE_POLYNOMIAL 0x1021U

/** 从0xFFFF开始计算CRC16-CCITT-FALSE。 */
uint16_t Crc16CcittFalse_Calculate(const uint8_t *data, size_t length);

/** 从调用方提供的CRC继续分段计算。 */
uint16_t Crc16CcittFalse_Update(uint16_t current_crc,
                               const uint8_t *data,
                               size_t length);

#endif /* CRC16_H */
