#pragma once

#include "esp_err.h"
#include "neko_controller.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t board_touch_init(void);
esp_err_t board_touch_poll(neko_touch_event_t *out_event);
esp_err_t board_touch_poll_point(int *out_x, int *out_y, bool *out_pressed);

#ifdef __cplusplus
}
#endif
