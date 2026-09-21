#include "neko_controller.h"

#include <stdio.h>
#include <string.h>

static bool time_reached(uint32_t now_ms, uint32_t deadline_ms)
{
    return (int32_t)(now_ms - deadline_ms) >= 0;
}

static void build_view(const neko_controller_t *controller,
                       const char *message,
                       neko_controller_view_t *view)
{
    view->message = message;
    view->summary = controller->summary;
    view->topics = controller->topics;
    view->topic_count = controller->topic_count;
    view->is_demo = controller->is_demo;
    view->duration_seconds = controller->duration_seconds;
    view->subject = controller->subject;
    view->trend_text = controller->trend_text;
    view->voice_level = controller->voice_level;
    view->voice_clipping = controller->voice_clipping;
    view->voice_quality = controller->voice_quality;
    view->card_index = controller->result_card_index;
    view->journey_step = controller->journey_step;
    view->journey_status = controller->journey_status;
    view->diagnostic_component = controller->diagnostic_component;
    view->diagnostic_status = controller->diagnostic_status;
}

static void render(neko_controller_t *controller, const char *message)
{
    neko_controller_view_t view;
    build_view(controller, message, &view);
    if (controller->callbacks.render_view != NULL) {
        controller->callbacks.render_view(controller->state, &view,
                                          controller->callbacks.user_data);
    } else if (controller->callbacks.render_state != NULL) {
        controller->callbacks.render_state(controller->state, message,
                                           controller->callbacks.user_data);
    }
}

static void set_state(neko_controller_t *controller,
                      neko_controller_state_t state,
                      const char *message)
{
    controller->state = state;
    render(controller, message);
}

static const char *command_name(neko_command_t command)
{
    switch (command) {
    case NEKO_COMMAND_START:
        return "start";
    case NEKO_COMMAND_PAUSE:
        return "pause";
    case NEKO_COMMAND_RESUME:
        return "resume";
    case NEKO_COMMAND_FINISH:
        return "finish";
    case NEKO_COMMAND_RETRY:
        return "retry";
    case NEKO_COMMAND_STATUS:
        return "status";
    case NEKO_COMMAND_DIAGNOSE:
        return "diagnose";
    case NEKO_COMMAND_CALIBRATE:
        return "calibrate";
    case NEKO_COMMAND_RECOVER:
        return "recover";
    case NEKO_COMMAND_DISCARD:
        return "discard";
    case NEKO_COMMAND_CANCEL:
        return "cancel";
    case NEKO_COMMAND_RESET:
        return "reset";
    case NEKO_COMMAND_NONE:
    default:
        return "";
    }
}

static void make_request_id(neko_controller_t *controller, char *out, size_t out_size)
{
    controller->request_counter++;
    snprintf(out, out_size, "%s-%lu", controller->boot_nonce,
             (unsigned long)controller->request_counter);
}

static void remember_last_command(neko_controller_t *controller,
                                  neko_command_t command,
                                  const char *request_id,
                                  const char *line)
{
    controller->last_command = command;
    snprintf(controller->last_command_request_id,
             sizeof(controller->last_command_request_id), "%s", request_id);
    snprintf(controller->last_command_line, sizeof(controller->last_command_line),
             "%s", line);
}

static void clear_session_result(neko_controller_t *controller)
{
    controller->summary[0] = '\0';
    controller->topic_count = 0;
    controller->result_request_id[0] = '\0';
    controller->heartbeat_request_id[0] = '\0';
    controller->result_deadline_ms = 0;
    controller->processing_max_deadline_ms = 0;
    controller->result_card_index = 0;
    controller->duration_seconds = 0;
    controller->subject[0] = '\0';
    controller->trend_text[0] = '\0';
    controller->journey_step[0] = '\0';
    controller->journey_status[0] = '\0';
    controller->diagnostic_component[0] = '\0';
    controller->diagnostic_status[0] = '\0';
    controller->confirmation_command = NEKO_COMMAND_NONE;
    controller->confirmation_event = 0;
}

static neko_controller_status_t send_line(neko_controller_t *controller,
                                          const char *line)
{
    if (controller->callbacks.send_line == NULL) {
        return NEKO_CONTROLLER_INVALID_ARGUMENT;
    }
    controller->callbacks.send_line(line, controller->callbacks.user_data);
    return NEKO_CONTROLLER_OK;
}

static neko_controller_status_t resend_last_command(neko_controller_t *controller,
                                                    uint32_t now_ms)
{
    if (controller->last_command_line[0] == '\0'
        || controller->last_command == NEKO_COMMAND_NONE) {
        return NEKO_CONTROLLER_INVALID_STATE;
    }
    if (send_line(controller, controller->last_command_line) != NEKO_CONTROLLER_OK) {
        return NEKO_CONTROLLER_INVALID_ARGUMENT;
    }
    controller->pending_command = controller->last_command;
    snprintf(controller->pending_request_id, sizeof(controller->pending_request_id),
             "%s", controller->last_command_request_id);
    controller->pending_deadline_ms = now_ms + NEKO_ACK_TIMEOUT_MS;
    set_state(controller, NEKO_CONTROLLER_PENDING, "reenviando comando");
    return NEKO_CONTROLLER_OK;
}

static neko_controller_status_t send_command(neko_controller_t *controller,
                                             neko_command_t command,
                                             int session_id,
                                             uint32_t now_ms,
                                             bool track_pending,
                                             bool heartbeat)
{
    char request_id[NEKO_REQUEST_ID_MAX + 1];
    char line[256];

    make_request_id(controller, request_id, sizeof(request_id));
    if (session_id > 0) {
        snprintf(line, sizeof(line),
                 "{\"v\":1,\"type\":\"command\",\"request_id\":\"%s\","
                 "\"command\":\"%s\",\"session_id\":%d}",
                 request_id, command_name(command), session_id);
    } else {
        snprintf(line, sizeof(line),
                 "{\"v\":1,\"type\":\"command\",\"request_id\":\"%s\","
                 "\"command\":\"%s\",\"session_id\":null}",
                 request_id, command_name(command));
    }
    if (send_line(controller, line) != NEKO_CONTROLLER_OK) {
        return NEKO_CONTROLLER_INVALID_ARGUMENT;
    }

    if (heartbeat) {
        snprintf(controller->heartbeat_request_id,
                 sizeof(controller->heartbeat_request_id), "%s", request_id);
    } else {
        remember_last_command(controller, command, request_id, line);
    }
    if (track_pending) {
        controller->pending_command = command;
        snprintf(controller->pending_request_id,
                 sizeof(controller->pending_request_id), "%s", request_id);
        controller->pending_deadline_ms = now_ms + NEKO_ACK_TIMEOUT_MS;
        set_state(controller, NEKO_CONTROLLER_PENDING, "aguardando Mac");
    }
    if (command == NEKO_COMMAND_FINISH || (command == NEKO_COMMAND_STATUS && !heartbeat)) {
        snprintf(controller->result_request_id,
                 sizeof(controller->result_request_id), "%s", request_id);
        controller->result_deadline_ms = now_ms + NEKO_RESULT_TIMEOUT_MS;
    }
    return NEKO_CONTROLLER_OK;
}

static bool touch_is_debounced(neko_controller_t *controller,
                               neko_touch_event_t event,
                               uint32_t now_ms)
{
    if (controller->last_touch_event == event
        && (uint32_t)(now_ms - controller->last_touch_ms) < NEKO_TOUCH_DEBOUNCE_MS) {
        return true;
    }
    controller->last_touch_event = event;
    controller->last_touch_ms = now_ms;
    return false;
}

static bool can_cancel(const neko_controller_t *controller)
{
    return controller->state == NEKO_CONTROLLER_CHECKING
        || controller->state == NEKO_CONTROLLER_READY
        || controller->state == NEKO_CONTROLLER_RECORDING
        || controller->state == NEKO_CONTROLLER_PAUSED
        || controller->state == NEKO_CONTROLLER_PROCESSING
        || controller->state == NEKO_CONTROLLER_RECOVERY;
}

static bool command_needs_confirmation(neko_command_t command)
{
    return command == NEKO_COMMAND_CANCEL
        || command == NEKO_COMMAND_DISCARD
        || command == NEKO_COMMAND_RESET;
}

static neko_controller_status_t confirm_or_send(neko_controller_t *controller,
                                                neko_touch_event_t event,
                                                neko_command_t command,
                                                int session_id,
                                                uint32_t now_ms)
{
    if (command_needs_confirmation(command)
        && (controller->confirmation_command != command
            || controller->confirmation_event != event)) {
        controller->confirmation_command = command;
        controller->confirmation_event = event;
        render(controller, "confirmar acao");
        return NEKO_CONTROLLER_OK;
    }
    controller->confirmation_command = NEKO_COMMAND_NONE;
    controller->confirmation_event = 0;
    if (command == NEKO_COMMAND_RESET) {
        clear_session_result(controller);
    }
    return send_command(controller, command, session_id, now_ms, true, false);
}

neko_controller_status_t neko_controller_init_with_boot_nonce(
    neko_controller_t *controller,
    const neko_controller_callbacks_t *callbacks,
    const char *boot_nonce)
{
    if (controller == NULL || callbacks == NULL || callbacks->send_line == NULL
        || boot_nonce == NULL || !neko_protocol_request_id_is_valid(boot_nonce)
        || strlen(boot_nonce) > (NEKO_REQUEST_ID_MAX - 12U)) {
        return NEKO_CONTROLLER_INVALID_ARGUMENT;
    }
    memset(controller, 0, sizeof(*controller));
    controller->callbacks = *callbacks;
    snprintf(controller->boot_nonce, sizeof(controller->boot_nonce), "%s",
             boot_nonce);
    controller->state = NEKO_CONTROLLER_IDLE;
    render(controller, "pronto");
    return NEKO_CONTROLLER_OK;
}

neko_controller_status_t neko_controller_init(
    neko_controller_t *controller,
    const neko_controller_callbacks_t *callbacks)
{
    return neko_controller_init_with_boot_nonce(controller, callbacks, "boot");
}

neko_controller_status_t neko_controller_touch(neko_controller_t *controller,
                                               neko_touch_event_t event,
                                               uint32_t now_ms)
{
    if (controller == NULL) {
        return NEKO_CONTROLLER_INVALID_ARGUMENT;
    }
    if (touch_is_debounced(controller, event, now_ms)) {
        render(controller, "toque ignorado");
        return NEKO_CONTROLLER_COMMAND_PENDING;
    }
    if (event == NEKO_TOUCH_RESEND) {
        return resend_last_command(controller, now_ms);
    }
    if (controller->pending_command != NEKO_COMMAND_NONE) {
        render(controller, "comando pendente");
        return NEKO_CONTROLLER_COMMAND_PENDING;
    }
    if (controller->confirmation_command != NEKO_COMMAND_NONE
        && controller->confirmation_event != event
        && event != NEKO_TOUCH_NEXT_CARD
        && event != NEKO_TOUCH_PREV_CARD) {
        controller->confirmation_command = NEKO_COMMAND_NONE;
        controller->confirmation_event = 0;
    }

    switch (event) {
    case NEKO_TOUCH_START:
        if (controller->state != NEKO_CONTROLLER_IDLE
            && controller->state != NEKO_CONTROLLER_READY) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        clear_session_result(controller);
        return send_command(controller, NEKO_COMMAND_START, 0, now_ms, true, false);
    case NEKO_TOUCH_DIAGNOSE:
        if (controller->state == NEKO_CONTROLLER_RECORDING
            || controller->state == NEKO_CONTROLLER_PAUSED
            || controller->state == NEKO_CONTROLLER_PROCESSING) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        return send_command(controller, NEKO_COMMAND_DIAGNOSE, controller->session_id,
                            now_ms, true, false);
    case NEKO_TOUCH_CALIBRATE:
        if (controller->state == NEKO_CONTROLLER_RECORDING
            || controller->state == NEKO_CONTROLLER_PAUSED
            || controller->state == NEKO_CONTROLLER_PROCESSING) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        return send_command(controller, NEKO_COMMAND_CALIBRATE, controller->session_id,
                            now_ms, true, false);
    case NEKO_TOUCH_PAUSE:
        if (controller->state != NEKO_CONTROLLER_RECORDING) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        return send_command(controller, NEKO_COMMAND_PAUSE, controller->session_id,
                            now_ms, true, false);
    case NEKO_TOUCH_RESUME:
        if (controller->state != NEKO_CONTROLLER_PAUSED) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        return send_command(controller, NEKO_COMMAND_RESUME, controller->session_id,
                            now_ms, true, false);
    case NEKO_TOUCH_FINISH:
        if (controller->state != NEKO_CONTROLLER_RECORDING
            && controller->state != NEKO_CONTROLLER_PAUSED) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        return send_command(controller, NEKO_COMMAND_FINISH, controller->session_id,
                            now_ms, true, false);
    case NEKO_TOUCH_RETRY:
        if (controller->state != NEKO_CONTROLLER_ERROR
            && controller->state != NEKO_CONTROLLER_SUCCESS
            && controller->state != NEKO_CONTROLLER_READY) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        clear_session_result(controller);
        return send_command(controller, NEKO_COMMAND_RETRY,
                            controller->previous_session_id > 0
                                ? controller->previous_session_id
                                : controller->session_id,
                            now_ms, true, false);
    case NEKO_TOUCH_STATUS:
        return send_command(controller, NEKO_COMMAND_STATUS, controller->session_id,
                            now_ms, true, false);
    case NEKO_TOUCH_RECOVER:
        if (controller->state != NEKO_CONTROLLER_RECOVERY) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        return send_command(controller, NEKO_COMMAND_RECOVER, controller->session_id,
                            now_ms, true, false);
    case NEKO_TOUCH_DISCARD:
        if (controller->state != NEKO_CONTROLLER_RECOVERY) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        return confirm_or_send(controller, event, NEKO_COMMAND_DISCARD,
                               controller->session_id, now_ms);
    case NEKO_TOUCH_CANCEL:
        if (!can_cancel(controller)) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        return confirm_or_send(controller, event, NEKO_COMMAND_CANCEL,
                               controller->session_id, now_ms);
    case NEKO_TOUCH_RESET:
        if (controller->state == NEKO_CONTROLLER_RECORDING
            || controller->state == NEKO_CONTROLLER_PAUSED
            || controller->state == NEKO_CONTROLLER_PROCESSING) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        return confirm_or_send(controller, event, NEKO_COMMAND_RESET,
                               controller->session_id, now_ms);
    case NEKO_TOUCH_NEXT_CARD:
        if (controller->state != NEKO_CONTROLLER_SUCCESS) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        controller->result_card_index++;
        render(controller, "proximo cartao");
        return NEKO_CONTROLLER_OK;
    case NEKO_TOUCH_PREV_CARD:
        if (controller->state != NEKO_CONTROLLER_SUCCESS) {
            return NEKO_CONTROLLER_INVALID_STATE;
        }
        if (controller->result_card_index > 0) {
            controller->result_card_index--;
        }
        render(controller, "cartao anterior");
        return NEKO_CONTROLLER_OK;
    case NEKO_TOUCH_RESEND:
    default:
        return NEKO_CONTROLLER_INVALID_ARGUMENT;
    }
}

static bool message_matches_session(const neko_controller_t *controller,
                                    const neko_mac_message_t *message)
{
    if (!message->has_session_id) {
        return false;
    }
    return controller->session_id > 0
        && message->session_id == controller->session_id;
}

static bool message_matches_pending(const neko_controller_t *controller,
                                    const neko_mac_message_t *message)
{
    return controller->pending_command != NEKO_COMMAND_NONE
        && strcmp(message->request_id, controller->pending_request_id) == 0;
}

static bool message_matches_heartbeat(const neko_controller_t *controller,
                                      const neko_mac_message_t *message)
{
    return controller->heartbeat_request_id[0] != '\0'
        && strcmp(message->request_id, controller->heartbeat_request_id) == 0;
}

static bool message_matches_result_request(const neko_controller_t *controller,
                                           const neko_mac_message_t *message)
{
    return controller->result_request_id[0] != '\0'
        && strcmp(message->request_id, controller->result_request_id) == 0;
}

static bool message_matches_last_command(const neko_controller_t *controller,
                                         const neko_mac_message_t *message)
{
    return controller->last_command_request_id[0] != '\0'
        && strcmp(message->request_id, controller->last_command_request_id) == 0;
}

static bool message_matches_active_request(const neko_controller_t *controller,
                                           const neko_mac_message_t *message)
{
    return message_matches_pending(controller, message)
        || message_matches_heartbeat(controller, message)
        || message_matches_result_request(controller, message)
        || message_matches_last_command(controller, message);
}

static void clear_pending(neko_controller_t *controller)
{
    controller->pending_command = NEKO_COMMAND_NONE;
    controller->pending_request_id[0] = '\0';
    controller->pending_deadline_ms = 0;
}

static bool pending_accepts_new_session(const neko_controller_t *controller)
{
    return controller->pending_command == NEKO_COMMAND_START
        || controller->pending_command == NEKO_COMMAND_RETRY;
}

static bool pending_state_is_expected(neko_command_t command, neko_mac_state_t state)
{
    switch (command) {
    case NEKO_COMMAND_START:
    case NEKO_COMMAND_RETRY:
        return state == NEKO_MAC_STATE_RECORDING
            || state == NEKO_MAC_STATE_IDLE
            || state == NEKO_MAC_STATE_PROCESSING;
    case NEKO_COMMAND_PAUSE:
        return state == NEKO_MAC_STATE_PAUSED;
    case NEKO_COMMAND_RESUME:
        return state == NEKO_MAC_STATE_RECORDING;
    case NEKO_COMMAND_FINISH:
        return state == NEKO_MAC_STATE_PROCESSING
            || state == NEKO_MAC_STATE_IDLE;
    case NEKO_COMMAND_STATUS:
        return state == NEKO_MAC_STATE_IDLE
            || state == NEKO_MAC_STATE_CHECKING
            || state == NEKO_MAC_STATE_READY
            || state == NEKO_MAC_STATE_RECORDING
            || state == NEKO_MAC_STATE_PAUSED
            || state == NEKO_MAC_STATE_PROCESSING
            || state == NEKO_MAC_STATE_RECOVERY;
    case NEKO_COMMAND_DIAGNOSE:
        return state == NEKO_MAC_STATE_CHECKING
            || state == NEKO_MAC_STATE_READY
            || state == NEKO_MAC_STATE_RECOVERY
            || state == NEKO_MAC_STATE_ERROR;
    case NEKO_COMMAND_CALIBRATE:
        return state == NEKO_MAC_STATE_CHECKING
            || state == NEKO_MAC_STATE_READY
            || state == NEKO_MAC_STATE_ERROR;
    case NEKO_COMMAND_RECOVER:
        return state == NEKO_MAC_STATE_READY
            || state == NEKO_MAC_STATE_RECORDING
            || state == NEKO_MAC_STATE_PROCESSING
            || state == NEKO_MAC_STATE_ERROR;
    case NEKO_COMMAND_DISCARD:
    case NEKO_COMMAND_CANCEL:
    case NEKO_COMMAND_RESET:
        return state == NEKO_MAC_STATE_IDLE
            || state == NEKO_MAC_STATE_READY
            || state == NEKO_MAC_STATE_ERROR;
    case NEKO_COMMAND_NONE:
    default:
        return false;
    }
}

static void apply_voice_if_due(neko_controller_t *controller,
                               const neko_mac_message_t *message,
                               uint32_t now_ms)
{
    if (!message->has_voice || !time_reached(now_ms, controller->next_voice_render_ms)) {
        return;
    }
    controller->voice_level = message->voice_level;
    controller->voice_clipping = message->voice_clipping;
    controller->voice_quality = message->voice_quality;
    controller->next_voice_render_ms = now_ms + NEKO_VOICE_RENDER_THROTTLE_MS;
}

static void refresh_processing_deadline(neko_controller_t *controller,
                                        const neko_mac_message_t *message,
                                        uint32_t now_ms)
{
    if (controller->processing_max_deadline_ms == 0) {
        controller->processing_max_deadline_ms = now_ms + NEKO_PROCESSING_MAX_MS;
    }
    if (message->has_journey_progress
        && !time_reached(now_ms, controller->processing_max_deadline_ms)) {
        controller->result_deadline_ms = now_ms + NEKO_RESULT_TIMEOUT_MS;
        if (time_reached(controller->result_deadline_ms,
                         controller->processing_max_deadline_ms)) {
            controller->result_deadline_ms = controller->processing_max_deadline_ms;
        }
    } else if (controller->result_deadline_ms == 0) {
        controller->result_deadline_ms = now_ms + NEKO_RESULT_TIMEOUT_MS;
    }
}

static neko_controller_status_t reject_unexpected_state(neko_controller_t *controller)
{
    clear_pending(controller);
    set_state(controller, NEKO_CONTROLLER_ERROR, "estado inesperado do Mac");
    return NEKO_CONTROLLER_INVALID_MESSAGE;
}

static neko_controller_status_t apply_state_message(neko_controller_t *controller,
                                                    const neko_mac_message_t *message,
                                                    uint32_t now_ms)
{
    bool from_pending = message_matches_pending(controller, message);
    bool from_heartbeat = message_matches_heartbeat(controller, message);
    bool from_last = message_matches_last_command(controller, message);

    if (!from_pending && !from_heartbeat && !from_last) {
        return NEKO_CONTROLLER_STALE;
    }
    if (from_pending
        && !pending_state_is_expected(controller->pending_command, message->state)) {
        return reject_unexpected_state(controller);
    }
    if (!message->has_session_id
        && message->state != NEKO_MAC_STATE_IDLE
        && message->state != NEKO_MAC_STATE_CHECKING
        && message->state != NEKO_MAC_STATE_READY) {
        return NEKO_CONTROLLER_STALE;
    }
    if (message->has_session_id
        && controller->session_id > 0 && !message_matches_session(controller, message)
        && !(from_pending && pending_accepts_new_session(controller))) {
        return NEKO_CONTROLLER_STALE;
    }
    if (from_pending && pending_accepts_new_session(controller)
        && message->has_session_id) {
        clear_session_result(controller);
        if (controller->session_id > 0) {
            controller->previous_session_id = controller->session_id;
        }
        controller->session_id = message->session_id;
    } else if (controller->session_id == 0 && message->has_session_id) {
        controller->session_id = message->session_id;
    }
    controller->is_demo = message->is_demo;
    apply_voice_if_due(controller, message, now_ms);
    if (message->journey_step[0] != '\0') {
        snprintf(controller->journey_step, sizeof(controller->journey_step), "%s",
                 message->journey_step);
    }
    if (message->journey_status[0] != '\0') {
        snprintf(controller->journey_status, sizeof(controller->journey_status), "%s",
                 message->journey_status);
    }
    if (message->diagnostic_component[0] != '\0') {
        snprintf(controller->diagnostic_component,
                 sizeof(controller->diagnostic_component), "%s",
                 message->diagnostic_component);
    }
    if (message->diagnostic_status[0] != '\0') {
        snprintf(controller->diagnostic_status, sizeof(controller->diagnostic_status),
                 "%s", message->diagnostic_status);
    }
    if (from_pending && message->state != NEKO_MAC_STATE_CHECKING) {
        clear_pending(controller);
    }
    if (from_heartbeat) {
        controller->heartbeat_request_id[0] = '\0';
    }
    controller->disconnect_deadline_ms = now_ms + NEKO_DISCONNECT_TIMEOUT_MS;
    /* Voice/progress events reuse the last command ID. They show the Mac is
     * alive, but must not postpone the ESP status command indefinitely. */
    if (from_pending || from_heartbeat) {
        controller->next_heartbeat_ms = now_ms + NEKO_HEARTBEAT_MS;
    }

    switch (message->state) {
    case NEKO_MAC_STATE_CHECKING:
        set_state(controller, NEKO_CONTROLLER_CHECKING, "verificando");
        return NEKO_CONTROLLER_OK;
    case NEKO_MAC_STATE_READY:
        set_state(controller, NEKO_CONTROLLER_READY, "pronto");
        return NEKO_CONTROLLER_OK;
    case NEKO_MAC_STATE_RECOVERY:
        if (!message->has_session_id) {
            return NEKO_CONTROLLER_STALE;
        }
        set_state(controller, NEKO_CONTROLLER_RECOVERY, "sessao interrompida");
        return NEKO_CONTROLLER_OK;
    case NEKO_MAC_STATE_RECORDING:
        set_state(controller, NEKO_CONTROLLER_RECORDING,
                  message->is_demo ? "demo gravando" : "gravando");
        return NEKO_CONTROLLER_OK;
    case NEKO_MAC_STATE_PAUSED:
        set_state(controller, NEKO_CONTROLLER_PAUSED, "pausado");
        return NEKO_CONTROLLER_OK;
    case NEKO_MAC_STATE_PROCESSING:
        refresh_processing_deadline(controller, message, now_ms);
        set_state(controller, NEKO_CONTROLLER_PROCESSING, "processando");
        return NEKO_CONTROLLER_OK;
    case NEKO_MAC_STATE_IDLE:
        if (!message->has_session_id) {
            controller->session_id = 0;
        }
        set_state(controller, NEKO_CONTROLLER_IDLE, "pronto");
        return NEKO_CONTROLLER_OK;
    case NEKO_MAC_STATE_ERROR:
        controller->previous_session_id = controller->session_id;
        set_state(controller, NEKO_CONTROLLER_ERROR, "erro");
        return NEKO_CONTROLLER_OK;
    case NEKO_MAC_STATE_COMPLETED:
    default:
        return NEKO_CONTROLLER_INVALID_MESSAGE;
    }
}

static neko_controller_status_t apply_result_message(neko_controller_t *controller,
                                                     const neko_mac_message_t *message,
                                                     uint32_t now_ms)
{
    size_t i;
    bool result_correlates = message_matches_result_request(controller, message)
        || message_matches_heartbeat(controller, message);
    if (!message_matches_session(controller, message)
        || !result_correlates
        || controller->result_deadline_ms == 0
        || time_reached(now_ms, controller->result_deadline_ms)) {
        return NEKO_CONTROLLER_STALE;
    }
    if (controller->state == NEKO_CONTROLLER_SUCCESS) {
        return NEKO_CONTROLLER_STALE;
    }
    controller->is_demo = message->is_demo;
    snprintf(controller->summary, sizeof(controller->summary), "%s", message->summary);
    controller->duration_seconds = message->duration_seconds;
    snprintf(controller->subject, sizeof(controller->subject), "%s", message->subject);
    snprintf(controller->trend_text, sizeof(controller->trend_text), "%s",
             message->trend_text);
    controller->topic_count = message->topic_count;
    for (i = 0; i < message->topic_count; i++) {
        snprintf(controller->topics[i], sizeof(controller->topics[i]), "%s",
                 message->topics[i]);
    }
    controller->previous_session_id = controller->session_id;
    clear_pending(controller);
    if (message_matches_heartbeat(controller, message)) {
        controller->heartbeat_request_id[0] = '\0';
    }
    controller->processing_max_deadline_ms = 0;
    set_state(controller, NEKO_CONTROLLER_SUCCESS,
              message->is_demo ? "demo concluida" : "sessao concluida");
    return NEKO_CONTROLLER_OK;
}

static neko_controller_status_t apply_error_message(neko_controller_t *controller,
                                                    const neko_mac_message_t *message)
{
    if (controller->state == NEKO_CONTROLLER_SUCCESS) {
        return NEKO_CONTROLLER_STALE;
    }
    if (!message->has_session_id) {
        if (!message_matches_pending(controller, message)
            || controller->pending_command != NEKO_COMMAND_START) {
            return NEKO_CONTROLLER_STALE;
        }
    } else if (controller->session_id > 0 && !message_matches_session(controller, message)) {
        return NEKO_CONTROLLER_STALE;
    }
    if (!message_matches_active_request(controller, message)) {
        return NEKO_CONTROLLER_STALE;
    }
    snprintf(controller->last_error, sizeof(controller->last_error), "%s",
             message->message);
    if (message->has_session_id) {
        controller->previous_session_id = message->session_id;
    }
    clear_pending(controller);
    controller->heartbeat_request_id[0] = '\0';
    set_state(controller, NEKO_CONTROLLER_ERROR, "erro do Mac");
    return NEKO_CONTROLLER_OK;
}

neko_controller_status_t neko_controller_receive(neko_controller_t *controller,
                                                 const char *line,
                                                 uint32_t now_ms)
{
    neko_mac_message_t message;
    neko_protocol_status_t parsed;

    if (controller == NULL || line == NULL) {
        return NEKO_CONTROLLER_INVALID_ARGUMENT;
    }
    parsed = neko_protocol_parse_mac_line(line, &message);
    if (parsed != NEKO_PROTOCOL_OK) {
        snprintf(controller->last_error, sizeof(controller->last_error),
                 "mensagem invalida: %s", neko_protocol_status_name(parsed));
        set_state(controller, NEKO_CONTROLLER_ERROR, "mensagem invalida");
        return NEKO_CONTROLLER_INVALID_MESSAGE;
    }

    switch (message.kind) {
    case NEKO_MAC_STATE:
        return apply_state_message(controller, &message, now_ms);
    case NEKO_MAC_RESULT:
        return apply_result_message(controller, &message, now_ms);
    case NEKO_MAC_ERROR:
        return apply_error_message(controller, &message);
    default:
        return NEKO_CONTROLLER_INVALID_MESSAGE;
    }
}

neko_controller_status_t neko_controller_tick(neko_controller_t *controller,
                                              uint32_t now_ms)
{
    if (controller == NULL) {
        return NEKO_CONTROLLER_INVALID_ARGUMENT;
    }
    if (controller->pending_command != NEKO_COMMAND_NONE
        && time_reached(now_ms, controller->pending_deadline_ms)) {
        clear_pending(controller);
        set_state(controller, NEKO_CONTROLLER_ERROR, "timeout do Mac");
        return NEKO_CONTROLLER_TIMEOUT;
    }
    if (controller->state == NEKO_CONTROLLER_PROCESSING
        && controller->result_deadline_ms > 0
        && time_reached(now_ms, controller->result_deadline_ms)) {
        controller->previous_session_id = controller->session_id;
        set_state(controller, NEKO_CONTROLLER_ERROR, "timeout da analise");
        return NEKO_CONTROLLER_TIMEOUT;
    }
    if ((controller->state == NEKO_CONTROLLER_RECORDING
         || controller->state == NEKO_CONTROLLER_PAUSED
         || controller->state == NEKO_CONTROLLER_PROCESSING)
        && controller->disconnect_deadline_ms > 0
        && time_reached(now_ms, controller->disconnect_deadline_ms)) {
        controller->previous_session_id = controller->session_id;
        set_state(controller, NEKO_CONTROLLER_ERROR, "serial desconectada");
        return NEKO_CONTROLLER_TIMEOUT;
    }
    if ((controller->state == NEKO_CONTROLLER_RECORDING
         || controller->state == NEKO_CONTROLLER_PAUSED
         || controller->state == NEKO_CONTROLLER_PROCESSING)
        && controller->pending_command == NEKO_COMMAND_NONE
        && controller->heartbeat_request_id[0] == '\0'
        && time_reached(now_ms, controller->next_heartbeat_ms)) {
        controller->next_heartbeat_ms = now_ms + NEKO_HEARTBEAT_MS;
        return send_command(controller, NEKO_COMMAND_STATUS, controller->session_id,
                            now_ms, false, true);
    }
    return NEKO_CONTROLLER_OK;
}

neko_controller_state_t neko_controller_state(const neko_controller_t *controller)
{
    return controller != NULL ? controller->state : NEKO_CONTROLLER_ERROR;
}

const char *neko_controller_state_name(neko_controller_state_t state)
{
    switch (state) {
    case NEKO_CONTROLLER_IDLE:
        return "IDLE";
    case NEKO_CONTROLLER_PENDING:
        return "PENDING";
    case NEKO_CONTROLLER_CHECKING:
        return "CHECKING";
    case NEKO_CONTROLLER_READY:
        return "READY";
    case NEKO_CONTROLLER_RECOVERY:
        return "RECOVERY";
    case NEKO_CONTROLLER_RECORDING:
        return "RECORDING";
    case NEKO_CONTROLLER_PAUSED:
        return "PAUSED";
    case NEKO_CONTROLLER_PROCESSING:
        return "PROCESSING";
    case NEKO_CONTROLLER_SUCCESS:
        return "SUCCESS";
    case NEKO_CONTROLLER_ERROR:
        return "ERROR";
    default:
        return "UNKNOWN";
    }
}

const char *neko_controller_summary(const neko_controller_t *controller)
{
    return controller != NULL ? controller->summary : "";
}

size_t neko_controller_topic_count(const neko_controller_t *controller)
{
    return controller != NULL ? controller->topic_count : 0;
}
