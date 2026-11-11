#pragma once

#include <stdint.h>

typedef void (*neko_avatar3d_pixel_fn)(int x, int y, uint16_t rgb565);

/* Geometria e luz calculadas a cada quadro no ESP; nenhum sprite ou GIF. */
void neko_avatar3d_render(int x, int y, int width, int height,
                          int clip_y0, int clip_y1,
                          const char *expression, uint32_t time_ms,
                          uint16_t background, neko_avatar3d_pixel_fn pixel);
