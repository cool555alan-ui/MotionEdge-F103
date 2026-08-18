#ifndef CONFIG_PERSISTENCE_H
#define CONFIG_PERSISTENCE_H
#include <stdbool.h>
#include <stdint.h>
#include "config_store.h"
bool ConfigPersistence_Init(uint32_t now_ms);
ConfigSaveStatus_t ConfigPersistence_Save(uint32_t now_ms);
ConfigSaveStatus_t ConfigPersistence_Load(void);
ConfigSaveStatus_t ConfigPersistence_FactoryReset(uint32_t now_ms);
#endif
