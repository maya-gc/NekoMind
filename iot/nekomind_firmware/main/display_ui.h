/**
 * display_ui.h - Interface do display LCD e do avatar ludico do NekoMind.
 *
 * No MVP o "display" e o proprio log serial (avatar em ASCII). Quando o
 * hardware do LCD for definido, apenas a funcao de renderizacao muda;
 * o restante do firmware continua chamando esta API.
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "esp_err.h"

#include "avatar_state.h"
#include "neko_layout.h"
#include "neko_protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------
 * TODO(hardware): pinos do LCD (SPI/I2C, DC, RST, CS, backlight...).
 * Preencha quando o modelo do display for escolhido.
 * ------------------------------------------------------------------ */
#define NEKO_LCD_PIN_MOSI  (-1) /* TODO */
#define NEKO_LCD_PIN_CLK   (-1) /* TODO */
#define NEKO_LCD_PIN_CS    (-1) /* TODO */
#define NEKO_LCD_PIN_DC    (-1) /* TODO */
#define NEKO_LCD_PIN_RST   (-1) /* TODO */
#define NEKO_LCD_PIN_BL    (-1) /* TODO */

/** Inicializa o display (ou o fallback em log). */
esp_err_t display_ui_init(void);

/**
 * Redesenha a tela conforme o estado atual do avatar.
 * Chamado periodicamente pela task de UI ou apos avatar_state_set().
 */
esp_err_t display_ui_render(const char *status_line);

/**
 * Renderiza estado com resultado validado quando houver. Drivers fisicos
 * futuros devem usar summary/topics/is_demo para mostrar a conclusao correta.
 */
esp_err_t display_ui_render_view(const char *status_line,
                                 const char *summary,
                                 const char (*topics)[NEKO_TOPIC_MAX + 1],
                                 size_t topic_count,
                                 bool is_demo,
                                 int duration_seconds,
                                 const char *trend_text,
                                 int voice_level,
                                 bool voice_clipping);
esp_err_t display_ui_draw_scene(const neko_scene_t *scene);

/** Mostra telemetria curta (ex.: RMS do microfone, heap livre). */
esp_err_t display_ui_show_telemetry(const char *telemetry_line);

#ifdef __cplusplus
}
#endif
