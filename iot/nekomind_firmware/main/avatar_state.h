/**
 * avatar_state.h - Maquina de estados do avatar/sessao NekoMind.
 *
 * Os estados refletem o ciclo de uma sessao de estudo (tecnica Feynman):
 * o estudante explica um tema em voz alta, o Mac captura o audio,
 * processa a sessao e devolve estado/resultado via serial.
 */
#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    NEKO_STATE_IDLE = 0,   /* Avatar aguardando, nenhuma sessao ativa      */
    NEKO_STATE_PENDING,    /* Comando enviado; aguardando confirmacao Mac  */
    NEKO_STATE_RECORDING,  /* Captura confirmada no microfone do Mac       */
    NEKO_STATE_PAUSED,     /* Captura pausada no Mac                       */
    NEKO_STATE_SENDING,    /* Envio/recebimento de comando serial          */
    NEKO_STATE_PROCESSING, /* Aguardando analise do backend               */
    NEKO_STATE_SUCCESS,    /* Sessao processada com sucesso               */
    NEKO_STATE_ERROR       /* Erro de captura, comunicacao ou analise     */
} neko_state_t;

/** Inicializa o controle de estado (estado inicial: IDLE). */
void avatar_state_init(void);

/** Define o estado atual e notifica o display/telemetria. */
void avatar_state_set(neko_state_t new_state);

/** Retorna o estado atual. */
neko_state_t avatar_state_get(void);

/** Nome legivel do estado (para logs e protocolo JSON). */
const char *avatar_state_name(neko_state_t state);

#ifdef __cplusplus
}
#endif
