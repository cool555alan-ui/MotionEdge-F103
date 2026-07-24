#ifndef BYTE_RING_BUFFER_H
#define BYTE_RING_BUFFER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct
{
    uint8_t *storage;
    size_t capacity;
    size_t head;
    size_t tail;
    size_t count;
    uint32_t overflow_count;
} ByteRingBuffer_t;

/** 使用调用方固定存储初始化字节环形缓冲。 */
bool ByteRingBuffer_Init(ByteRingBuffer_t *buffer,
                         uint8_t *storage,
                         size_t capacity);
/** 入队一个字节；满时拒绝且累计overflow_count。 */
bool ByteRingBuffer_Push(ByteRingBuffer_t *buffer, uint8_t byte);
/** 弹出最早字节。 */
bool ByteRingBuffer_Pop(ByteRingBuffer_t *buffer, uint8_t *byte);
/** 查看指定偏移字节但不弹出。 */
bool ByteRingBuffer_Peek(const ByteRingBuffer_t *buffer,
                         size_t offset,
                         uint8_t *byte);
size_t ByteRingBuffer_Size(const ByteRingBuffer_t *buffer);
size_t ByteRingBuffer_FreeSpace(const ByteRingBuffer_t *buffer);
void ByteRingBuffer_Clear(ByteRingBuffer_t *buffer);

#endif /* BYTE_RING_BUFFER_H */
