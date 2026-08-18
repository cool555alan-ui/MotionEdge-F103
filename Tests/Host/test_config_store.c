#include "config_store.h"

#include <string.h>

#include "crc16.h"
#include "test_support.h"

static uint8_t s_flash[2U * CONFIG_FLASH_PAGE_SIZE];
static int32_t s_program_limit;
static bool s_erase_fail;
static bool s_read_mismatch;

static size_t Offset(uint32_t address) { return (size_t)(address-CONFIG_SLOT_A_ADDRESS); }
static void Put16(uint8_t *p,uint16_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8U);}
static void Put32(uint8_t *p,uint32_t v){Put16(p,(uint16_t)v);Put16(p+2,(uint16_t)(v>>16U));}
static void Recrc(uint8_t *slot){Put16(slot+50U,Crc16CcittFalse_Calculate(slot,50U));}
static bool Read(uint32_t address,uint8_t *data,size_t length)
{
    if(data==NULL||Offset(address)+length>sizeof(s_flash))return false;
    memcpy(data,&s_flash[Offset(address)],length);
    if(s_read_mismatch&&length>0U)data[0]^=1U;
    return true;
}
static bool Erase(uint32_t address)
{
    if(s_erase_fail||((address!=CONFIG_SLOT_A_ADDRESS)&&(address!=CONFIG_SLOT_B_ADDRESS)))return false;
    memset(&s_flash[Offset(address)],0xFF,CONFIG_FLASH_PAGE_SIZE); return true;
}
static bool Program(uint32_t address,const uint8_t *data,size_t length)
{
    size_t i,n=length;
    if(data==NULL||Offset(address)+length>sizeof(s_flash))return false;
    if(s_program_limit>=0&&(size_t)s_program_limit<n)n=(size_t)s_program_limit;
    for(i=0U;i<n;i++)s_flash[Offset(address)+i]&=data[i];
    return n==length;
}
static void Reset(void)
{
    memset(s_flash,0xFF,sizeof(s_flash)); s_program_limit=-1; s_erase_fail=false; s_read_mismatch=false;
}

void TestConfigStore_Run(TestContext_t *context)
{
    const ConfigFlashBackend_t backend={Read,Erase,Program,NULL};
    PersistentConfigV1_t c,loaded; ConfigStoreStatus_t status;
    Reset();
    TEST_EXPECT(context,ConfigStore_Init(&backend,0U,&loaded));
    TEST_EXPECT(context,loaded.deadband_cdeg==100U&&loaded.pid_axis==1U&&loaded.kd_milli==50U);
    TEST_EXPECT(context,ConfigStore_GetStatus(&status)&&status.loaded_from==CONFIG_SOURCE_DEFAULTS&&status.valid_slot_count==0U);
    TEST_EXPECT(context,ConfigStore_Save(&loaded,10U,false)==CONFIG_SAVE_BUSY);
    c=loaded; c.servo_min_us=1400U; TEST_EXPECT(context,!ConfigStore_IsConfigValid(&c));
    c=loaded; c.output_max_us=11; TEST_EXPECT(context,!ConfigStore_IsConfigValid(&c));
    c=loaded; c.kp_milli=50001U; TEST_EXPECT(context,!ConfigStore_IsConfigValid(&c));
    c=loaded; c.low_pass_alpha_milli=0U; TEST_EXPECT(context,!ConfigStore_IsConfigValid(&c));
    c=loaded; c.deadband_cdeg=150U;
    TEST_EXPECT(context,ConfigStore_Save(&c,10U,true)==CONFIG_SAVE_OK);
    TEST_EXPECT(context,ConfigStore_GetStatus(&status)&&status.loaded_from==CONFIG_SOURCE_SLOT_A&&status.generation==1U&&!status.dirty);
    TEST_EXPECT(context,ConfigStore_Save(&c,20U,true)==CONFIG_SAVE_RATE_LIMITED);
    TEST_EXPECT(context,ConfigStore_Init(&backend,6000U,&loaded)&&loaded.deadband_cdeg==150U);
    c.deadband_cdeg=200U; TEST_EXPECT(context,ConfigStore_Save(&c,6000U,true)==CONFIG_SAVE_OK);
    TEST_EXPECT(context,ConfigStore_GetStatus(&status)&&status.loaded_from==CONFIG_SOURCE_SLOT_B&&status.generation==2U);
    TEST_EXPECT(context,ConfigStore_Init(&backend,12000U,&loaded)&&loaded.deadband_cdeg==200U);
    Put32(s_flash+10U,0xFFFFFFFFU);Put32(s_flash+CONFIG_FLASH_PAGE_SIZE+10U,0U);Recrc(s_flash);Recrc(s_flash+CONFIG_FLASH_PAGE_SIZE);
    TEST_EXPECT(context,ConfigStore_Init(&backend,12000U,&loaded)&&loaded.deadband_cdeg==200U);
    Put16(s_flash+CONFIG_FLASH_PAGE_SIZE+4U,2U);Recrc(s_flash+CONFIG_FLASH_PAGE_SIZE);
    TEST_EXPECT(context,ConfigStore_Init(&backend,12000U,&loaded)&&loaded.deadband_cdeg==150U);
    TEST_EXPECT(context,ConfigStore_GetStatus(&status)&&status.unsupported_schema_count==1U);
    Put16(s_flash+CONFIG_FLASH_PAGE_SIZE+4U,1U);Put32(s_flash+CONFIG_FLASH_PAGE_SIZE+10U,2U);Recrc(s_flash+CONFIG_FLASH_PAGE_SIZE);
    s_flash[CONFIG_FLASH_PAGE_SIZE+50U]^=1U;
    TEST_EXPECT(context,ConfigStore_Init(&backend,18000U,&loaded)&&loaded.deadband_cdeg==150U);
    s_flash[52U]=0xFFU; s_flash[53U]=0xFFU;
    TEST_EXPECT(context,ConfigStore_Init(&backend,24000U,&loaded)&&loaded.deadband_cdeg==100U);

    Reset(); TEST_EXPECT(context,ConfigStore_Init(&backend,0U,&loaded));
    s_program_limit=12; TEST_EXPECT(context,ConfigStore_Save(&loaded,0U,true)==CONFIG_SAVE_PROGRAM_FAILED);
    s_program_limit=-1; TEST_EXPECT(context,ConfigStore_Init(&backend,0U,&c)&&c.deadband_cdeg==100U);
    s_erase_fail=true; TEST_EXPECT(context,ConfigStore_Save(&c,6000U,true)==CONFIG_SAVE_ERASE_FAILED);
    s_erase_fail=false; s_read_mismatch=true; TEST_EXPECT(context,ConfigStore_Save(&c,6000U,true)==CONFIG_SAVE_VERIFY_FAILED);
    s_read_mismatch=false; TEST_EXPECT(context,ConfigStore_Save(&c,6000U,true)==CONFIG_SAVE_OK);
    ConfigStore_MarkDirty(); TEST_EXPECT(context,ConfigStore_GetStatus(&status)&&status.dirty);
    TEST_EXPECT(context,ConfigStore_FactoryReset(12000U,false,&loaded)==CONFIG_SAVE_BUSY);
    TEST_EXPECT(context,ConfigStore_FactoryReset(12000U,true,&loaded)==CONFIG_SAVE_OK);
    TEST_EXPECT(context,loaded.deadband_cdeg==100U&&ConfigStore_GetStatus(&status)&&status.valid_slot_count==0U);
    TEST_EXPECT(context,ConfigStore_Init(&backend,0U,&loaded)&&status.schema_version==CONFIG_SCHEMA_VERSION);
}
