#include "byte_ring_buffer.h"

#include <stddef.h>

bool ByteRingBuffer_Init(ByteRingBuffer_t *buffer,
                         uint8_t *storage,
                         size_t capacity)
{
    if ((buffer == NULL) || (storage == NULL) || (capacity == 0U))
    {
        return false;
    }
    buffer->storage = storage;
    buffer->capacity = capacity;
    buffer->head = 0U;
    buffer->tail = 0U;
    buffer->count = 0U;
    buffer->overflow_count = 0U;
    return true;
}

bool ByteRingBuffer_Push(ByteRingBuffer_t *buffer, uint8_t byte)
{
    if ((buffer == NULL) || (buffer->storage == NULL) ||
        (buffer->capacity == 0U))
    {
        return false;
    }
    if (buffer->count == buffer->capacity)
    {
        ++buffer->overflow_count;
        return false;
    }
    buffer->storage[buffer->head] = byte;
    buffer->head = (buffer->head + 1U) % buffer->capacity;
    ++buffer->count;
    return true;
}

bool ByteRingBuffer_Pop(ByteRingBuffer_t *buffer, uint8_t *byte)
{
    if ((buffer == NULL) || (byte == NULL) || (buffer->storage == NULL) ||
        (buffer->count == 0U))
    {
        return false;
    }
    *byte = buffer->storage[buffer->tail];
    buffer->tail = (buffer->tail + 1U) % buffer->capacity;
    --buffer->count;
    return true;
}

bool ByteRingBuffer_Peek(const ByteRingBuffer_t *buffer,
                         size_t offset,
                         uint8_t *byte)
{
    if ((buffer == NULL) || (byte == NULL) || (buffer->storage == NULL) ||
        (offset >= buffer->count))
    {
        return false;
    }
    *byte = buffer->storage[(buffer->tail + offset) % buffer->capacity];
    return true;
}

size_t ByteRingBuffer_Size(const ByteRingBuffer_t *buffer)
{
    return (buffer == NULL) ? 0U : buffer->count;
}

size_t ByteRingBuffer_FreeSpace(const ByteRingBuffer_t *buffer)
{
    if ((buffer == NULL) || (buffer->count > buffer->capacity))
    {
        return 0U;
    }
    return buffer->capacity - buffer->count;
}

void ByteRingBuffer_Clear(ByteRingBuffer_t *buffer)
{
    if (buffer != NULL)
    {
        buffer->head = 0U;
        buffer->tail = 0U;
        buffer->count = 0U;
    }
}
