#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "neko_protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

#define NEKO_ACK_TIMEOUT_MS 5000U
#define NEKO_RESULT_TIMEOUT_MS 120000U
#define NEKO_PROCESSING_MAX_MS 600000U
#define NEKO_HEARTBEAT_MS 2000U
#define NEKO_DISCONNECT_TIMEOUT_MS 8000U
#define NEKO_TOUCH_DEBOUNCE_MS 250U
#define NEKO_VOICE_RENDER_THROTTLE_MS 200U

typedef enum {
    NEKO_CONTROLLER_IDLE = 0,
    NEKO_CONTROLLER_PENDING,
    NEKO_CONTROLLER_CHECKING,
    NEKO_CONTROLLER_READY,
    NEKO_CONTROLLER_RECOVERY,
    NEKO_CONTROLLER_RECORDING,
    NEKO_CONTROLLER_PAUSED,
    NEKO_CONTROLLER_PROCESSING,
    NEKO_CONTROLLER_SUCCESS,
    NEKO_CONTROLLER_ERROR
} neko_controller_state_t;

typedef enum {
    NEKO_TOUCH_START = 1,
    NEKO_TOUCH_PAUSE,
    NEKO_TOUCH_RESUME,
    NEKO_TOUCH_FINISH,
    NEKO_TOUCH_RETRY,
    NEKO_TOUCH_STATUS,
    NEKO_TOUCH_RESEND,
    NEKO_TOUCH_DIAGNOSE,
    NEKO_TOUCH_CALIBRATE,
    NEKO_TOUCH_RECOVER,
    NEKO_TOUCH_DISCARD,
    NEKO_TOUCH_CANCEL,
    NEKO_TOUCH_RESET,
    NEKO_TOUCH_NEXT_CARD,
    NEKO_TOUCH_PREV_CARD,
    NEKO_TOUCH_THEME /* local ao display; nunca enviado ao Mac */
} neko_touch_event_t;

typedef enum {
    NEKO_COMMAND_NONE = 0,
    NEKO_COMMAND_START,
    NEKO_COMMAND_PAUSE,
    NEKO_COMMAND_RESUME,
    NEKO_COMMAND_FINISH,
    NEKO_COMMAND_RETRY,
    NEKO_COMMAND_STATUS,
    NEKO_COMMAND_DIAGNOSE,
    NEKO_COMMAND_CALIBRATE,
    NEKO_COMMAND_RECOVER,
    NEKO_COMMAND_DISCARD,
    NEKO_COMMAND_CANCEL,
    NEKO_COMMAND_RESET
} neko_command_t;

typedef enum {
    NEKO_CONTROLLER_OK = 0,
    NEKO_CONTROLLER_INVALID_ARGUMENT,
    NEKO_CONTROLLER_INVALID_STATE,
    NEKO_CONTROLLER_COMMAND_PENDING,
    NEKO_CONTROLLER_INVALID_MESSAGE,
    NEKO_CONTROLLER_STALE,
    NEKO_CONTROLLER_TIMEOUT
} neko_controller_status_t;

typedef void (*neko_controller_send_line_fn)(const char *line, void *user_data);
typedef struct {
    const char *message;
    const char *summary;
    const char (*topics)[NEKO_TOPIC_MAX + 1];
    size_t topic_count;
    bool is_demo;
    int duration_seconds;
    const char *subject;
    const char *trend_text;
    int voice_level;
    bool voice_clipping;
    neko_voice_quality_t voice_quality;
    size_t card_index;
    const char *journey_step;
    const char *journey_status;
    const char *diagnostic_component;
    const char *diagnostic_status;
} neko_controller_view_t;

typedef void (*neko_controller_render_fn)(neko_controller_state_t state,
                                          const char *message,
                                          void *user_data);
typedef void (*neko_controller_render_view_fn)(neko_controller_state_t state,
                                               const neko_controller_view_t *view,
                                               void *user_data);

typedef struct {
    neko_controller_send_line_fn send_line;
    neko_controller_render_fn render_state;
    neko_controller_render_view_fn render_view;
    void *user_data;
} neko_controller_callbacks_t;

typedef struct {
    neko_controller_state_t state;
    neko_controller_callbacks_t callbacks;
    uint32_t request_counter;
    int session_id;
    int previous_session_id;
    bool is_demo;
    char boot_nonce[NEKO_REQUEST_ID_MAX + 1];
    neko_command_t pending_command;
    char pending_request_id[NEKO_REQUEST_ID_MAX + 1];
    char result_request_id[NEKO_REQUEST_ID_MAX + 1];
    char heartbeat_request_id[NEKO_REQUEST_ID_MAX + 1];
    neko_command_t last_command;
    char last_command_request_id[NEKO_REQUEST_ID_MAX + 1];
    char last_command_line[256];
    uint32_t pending_deadline_ms;
    uint32_t result_deadline_ms;
    uint32_t processing_max_deadline_ms;
    uint32_t next_heartbeat_ms;
    uint32_t disconnect_deadline_ms;
    char summary[NEKO_RESULT_SUMMARY_MAX + 1];
    char topics[NEKO_TOPIC_COUNT_MAX][NEKO_TOPIC_MAX + 1];
    size_t topic_count;
    char last_error[NEKO_ERROR_MESSAGE_MAX + 1];
    uint32_t last_touch_ms;
    neko_touch_event_t last_touch_event;
    uint32_t next_voice_render_ms;
    int voice_level;
    bool voice_clipping;
    neko_voice_quality_t voice_quality;
    size_t result_card_index;
    int duration_seconds;
    char subject[NEKO_SUBJECT_MAX + 1];
    char trend_text[NEKO_TREND_TEXT_MAX + 1];
    char journey_step[NEKO_JOURNEY_TEXT_MAX + 1];
    char journey_status[NEKO_JOURNEY_TEXT_MAX + 1];
    char diagnostic_component[NEKO_DIAGNOSTIC_TEXT_MAX + 1];
    char diagnostic_status[NEKO_DIAGNOSTIC_TEXT_MAX + 1];
    neko_command_t confirmation_command;
    neko_touch_event_t confirmation_event;
} neko_controller_t;

neko_controller_status_t neko_controller_init(
    neko_controller_t *controller,
    const neko_controller_callbacks_t *callbacks);
neko_controller_status_t neko_controller_init_with_boot_nonce(
    neko_controller_t *controller,
    const neko_controller_callbacks_t *callbacks,
    const char *boot_nonce);
neko_controller_status_t neko_controller_touch(neko_controller_t *controller,
                                               neko_touch_event_t event,
                                               uint32_t now_ms);
neko_controller_status_t neko_controller_receive(neko_controller_t *controller,
                                                 const char *line,
                                                 uint32_t now_ms);
neko_controller_status_t neko_controller_tick(neko_controller_t *controller,
                                              uint32_t now_ms);
neko_controller_state_t neko_controller_state(const neko_controller_t *controller);
const char *neko_controller_state_name(neko_controller_state_t state);
const char *neko_controller_summary(const neko_controller_t *controller);
size_t neko_controller_topic_count(const neko_controller_t *controller);

#ifdef __cplusplus
}
#endif
