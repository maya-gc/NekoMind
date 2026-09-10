#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define NEKO_PROTOCOL_MAX_LINE_BYTES 4096
#define NEKO_REQUEST_ID_MAX 64
#define NEKO_RESULT_SUMMARY_MAX 240
#define NEKO_TOPIC_MAX 120
#define NEKO_TOPIC_COUNT_MAX 8
#define NEKO_PROVIDER_MAX 64
#define NEKO_ERROR_CODE_MAX 64
#define NEKO_ERROR_MESSAGE_MAX 160

typedef enum {
    NEKO_PROTOCOL_OK = 0,
    NEKO_PROTOCOL_ERR_NULL,
    NEKO_PROTOCOL_ERR_TOO_LONG,
    NEKO_PROTOCOL_ERR_JSON,
    NEKO_PROTOCOL_ERR_DUPLICATE_KEY,
    NEKO_PROTOCOL_ERR_MISSING_FIELD,
    NEKO_PROTOCOL_ERR_INVALID_FIELD
} neko_protocol_status_t;

typedef enum {
    NEKO_MAC_STATE = 1,
    NEKO_MAC_RESULT,
    NEKO_MAC_ERROR
} neko_mac_message_kind_t;

typedef enum {
    NEKO_MAC_STATE_IDLE = 1,
    NEKO_MAC_STATE_RECORDING,
    NEKO_MAC_STATE_PAUSED,
    NEKO_MAC_STATE_PROCESSING,
    NEKO_MAC_STATE_COMPLETED,
    NEKO_MAC_STATE_ERROR
} neko_mac_state_t;

typedef struct {
    neko_mac_message_kind_t kind;
    char request_id[NEKO_REQUEST_ID_MAX + 1];
    int session_id;
    bool has_session_id;
    neko_mac_state_t state;
    bool is_demo;
    char asr_provider[NEKO_PROVIDER_MAX + 1];
    char topic_provider[NEKO_PROVIDER_MAX + 1];
    char topics[NEKO_TOPIC_COUNT_MAX][NEKO_TOPIC_MAX + 1];
    size_t topic_count;
    char summary[NEKO_RESULT_SUMMARY_MAX + 1];
    char code[NEKO_ERROR_CODE_MAX + 1];
    char message[NEKO_ERROR_MESSAGE_MAX + 1];
} neko_mac_message_t;

bool neko_protocol_request_id_is_valid(const char *request_id);
neko_protocol_status_t neko_protocol_parse_mac_line(const char *line,
                                                    neko_mac_message_t *out);
const char *neko_protocol_status_name(neko_protocol_status_t status);

#ifdef __cplusplus
}
#endif
