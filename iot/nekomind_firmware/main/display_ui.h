/**
 * display_ui.h - Interface do display LCD e do avatar ludico do NekoMind.
 *
 * Renderizador para o LCD ILI9341 240x320 do prototipo ESP32-S3.
 * A logica de estados e layout permanece independente do driver fisico.
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

/** Inicializa o display fisico. */
esp_err_t display_ui_init(void);

/**
 * Redesenha a tela conforme o estado atual do avatar.
 * Chamado periodicamente pela task de UI ou apos avatar_state_set().
 */
esp_err_t display_ui_render(const char *status_line);

/**
 * API legada de texto curto. O fluxo principal renderiza a cena completa via
 * display_ui_draw_scene() a partir do controlador de sessao.
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
esp_err_t display_ui_calibration_step(int step);

/** Mostra telemetria curta (ex.: RMS do microfone, heap livre). */
esp_err_t display_ui_show_telemetry(const char *telemetry_line);

#ifdef __cplusplus
}
#endif
