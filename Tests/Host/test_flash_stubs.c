#include "bsp_flash.h"

static bool Read(uint32_t address,uint8_t *data,size_t length)
{ (void)address; while(length-- > 0U)*data++=0xFFU; return true; }
static bool Erase(uint32_t address) { (void)address; return true; }
static bool Program(uint32_t address,const uint8_t *data,size_t length)
{ (void)address;(void)data;(void)length;return true; }
const ConfigFlashBackend_t *BspFlash_GetConfigBackend(void)
{ static const ConfigFlashBackend_t backend={Read,Erase,Program,NULL};return &backend; }
