#include "bsp_flash.h"
#include <string.h>
#include "stm32f1xx_hal.h"

static bool Read(uint32_t address,uint8_t *data,size_t length)
{
    if(data==NULL||address<CONFIG_SLOT_A_ADDRESS||address+length>CONFIG_SLOT_B_ADDRESS+CONFIG_FLASH_PAGE_SIZE)return false;
    memcpy(data,(const void *)address,length); return true;
}
static bool Erase(uint32_t address)
{
    FLASH_EraseInitTypeDef e={0}; uint32_t error=0U; HAL_StatusTypeDef result;
    if(address!=CONFIG_SLOT_A_ADDRESS&&address!=CONFIG_SLOT_B_ADDRESS)return false;
    if(HAL_FLASH_Unlock()!=HAL_OK)return false;
    e.TypeErase=FLASH_TYPEERASE_PAGES; e.PageAddress=address; e.NbPages=1U;
    result=HAL_FLASHEx_Erase(&e,&error); (void)HAL_FLASH_Lock(); return result==HAL_OK;
}
static bool Program(uint32_t address,const uint8_t *data,size_t length)
{
    size_t i; HAL_StatusTypeDef result=HAL_OK;
    if(data==NULL||(length&1U)!=0U||address<CONFIG_SLOT_A_ADDRESS||address+length>CONFIG_SLOT_B_ADDRESS+CONFIG_FLASH_PAGE_SIZE)return false;
    if(HAL_FLASH_Unlock()!=HAL_OK)return false;
    for(i=0U;i<length;i+=2U){uint16_t value=(uint16_t)data[i]|((uint16_t)data[i+1U]<<8U); if(HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD,address+(uint32_t)i,value)!=HAL_OK){result=HAL_ERROR;break;}}
    (void)HAL_FLASH_Lock(); return result==HAL_OK;
}
static uint32_t TimeMs(void) { return HAL_GetTick(); }
const ConfigFlashBackend_t *BspFlash_GetConfigBackend(void)
{
    static const ConfigFlashBackend_t backend={Read,Erase,Program,TimeMs}; return &backend;
}
