#ifndef APP_MAIN_H
#define APP_MAIN_H

#include <stdbool.h>
#include <stdint.h>

bool App_Init(uint32_t now_ms);
void App_RunOnce(uint32_t now_ms);

#endif /* APP_MAIN_H */
