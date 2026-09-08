/**
 * display_ui.h - Interface do display LCD e do avatar ludico do NekoMind.
 *
 * No MVP o "display" e o proprio log serial (avatar em ASCII). Quando o
 * hardware do LCD for definido, apenas a funcao de renderizacao muda;
 * o restante do firmware continua chamando esta API.
 */
#pragma once

#include "esp_err.h"

#include "avatar_state.h"

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

/** Mostra telemetria curta (ex.: RMS do microfone, heap livre). */
esp_err_t display_ui_show_telemetry(const char *telemetry_line);

#ifdef __cplusplus
}
#endif
