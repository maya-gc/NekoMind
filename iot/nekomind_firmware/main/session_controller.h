/**
 * session_controller.h - Orquestra a sessao touch + Mac.
 *
 * O firmware envia comandos JSON Lines pela serial e so muda para gravando,
 * processando ou sucesso depois de estados/resultados correlacionados do Mac.
 * Audio nao trafega pelo ESP no caminho principal do MVP.
 */
#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Inicializa todos os modulos e entra em IDLE. */
esp_err_t session_controller_init(void);

/** Inicia a task FreeRTOS do controlador (loop de eventos). */
esp_err_t session_controller_start_task(void);

#ifdef __cplusplus
}
#endif
