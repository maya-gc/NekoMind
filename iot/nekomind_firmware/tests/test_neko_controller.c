#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../main/neko_controller.h"
#include "../main/neko_layout.h"
#include "../main/neko_protocol.h"

typedef struct {
    char lines[16][512];
    int line_count;
    neko_controller_state_t rendered[32];
    char summaries[32][NEKO_RESULT_SUMMARY_MAX + 1];
    int durations[32];
    char trends[32][NEKO_TREND_TEXT_MAX + 1];
    size_t card_indices[32];
    bool demos[32];
    int render_count;
} fake_io_t;

static void fake_send(const char *line, void *user_data)
{
    fake_io_t *io = (fake_io_t *)user_data;
    assert(io->line_count < 16);
    snprintf(io->lines[io->line_count], sizeof(io->lines[io->line_count]), "%s", line);
    io->line_count++;
}

static void fake_render(neko_controller_state_t state, const char *message, void *user_data)
{
    fake_io_t *io = (fake_io_t *)user_data;
    assert(io->render_count < 32);
    io->rendered[io->render_count++] = state;
    snprintf(io->summaries[io->render_count - 1], sizeof(io->summaries[0]), "%s",
             message != NULL ? message : "");
}

static void fake_render_result(neko_controller_state_t state,
                               const neko_controller_view_t *view,
                               void *user_data)
{
    fake_io_t *io = (fake_io_t *)user_data;
    assert(io->render_count < 32);
    io->rendered[io->render_count] = state;
    io->demos[io->render_count] = view != NULL && view->is_demo;
    io->durations[io->render_count] = view != NULL ? view->duration_seconds : 0;
    io->card_indices[io->render_count] = view != NULL ? view->card_index : 0;
    snprintf(io->trends[io->render_count], sizeof(io->trends[0]), "%s",
             view != NULL && view->trend_text != NULL ? view->trend_text : "");
    snprintf(io->summaries[io->render_count], sizeof(io->summaries[0]), "%s",
             view != NULL && view->summary != NULL ? view->summary : "");
    io->render_count++;
}

static void init_controller_with_nonce(neko_controller_t *controller, fake_io_t *io,
                                       const char *boot_nonce)
{
    memset(io, 0, sizeof(*io));
    neko_controller_callbacks_t callbacks = {
        .send_line = fake_send,
        .render_state = fake_render,
        .render_view = fake_render_result,
        .user_data = io,
    };
    assert(neko_controller_init_with_boot_nonce(controller, &callbacks, boot_nonce)
        == NEKO_CONTROLLER_OK);
}

static void init_controller(neko_controller_t *controller, fake_io_t *io)
{
    init_controller_with_nonce(controller, io, "boot");
}

static void test_valid_completion_requires_correlated_result(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 1000) == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[0], "\"command\":\"start\"") != NULL);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":42,"
        "\"state\":\"recording\",\"is_demo\":false}", 1100) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_RECORDING);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_FINISH, 1200) == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[1], "\"command\":\"finish\"") != NULL);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":42,"
        "\"state\":\"processing\",\"is_demo\":false}", 1300) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_PROCESSING);

    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"boot-2\",\"session_id\":42,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local-keyword\",\"topics\":[\"fotossintese\",\"clorofila\"],"
        "\"summary\":\"Sessao processada.\"}", 1400) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_SUCCESS);
    assert(strcmp(neko_controller_summary(&controller), "Sessao processada.") == 0);
    assert(neko_controller_topic_count(&controller) == 2);
    assert(strcmp(io.summaries[io.render_count - 1], "Sessao processada.") == 0);
    assert(!io.demos[io.render_count - 1]);
}

static void test_invalid_stale_and_wrong_session_results_do_not_succeed(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":7,"
        "\"state\":\"recording\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_FINISH, 20) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":7,"
        "\"state\":\"processing\",\"is_demo\":false}", 30) == NEKO_CONTROLLER_OK);

    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"old\",\"session_id\":7,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[],\"summary\":\"Antigo.\"}", 40)
        == NEKO_CONTROLLER_STALE);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_PROCESSING);

    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"boot-2\",\"session_id\":8,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[],\"summary\":\"Outra sessao.\"}", 50)
        == NEKO_CONTROLLER_STALE);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_PROCESSING);

    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"boot-2\",\"session_id\":7,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"mock\","
        "\"topic_provider\":\"local\",\"topics\":[],\"summary\":\"Mock real.\"}", 60)
        == NEKO_CONTROLLER_INVALID_MESSAGE);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_ERROR);
}

static void test_pending_timeout_processing_timeout_and_late_result(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_tick(&controller, 5001) == NEKO_CONTROLLER_TIMEOUT);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_ERROR);

    init_controller(&controller, &io);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":4,"
        "\"state\":\"recording\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_FINISH, 20) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":4,"
        "\"state\":\"processing\",\"is_demo\":false}", 30) == NEKO_CONTROLLER_OK);
    assert(neko_controller_tick(&controller, 120031) == NEKO_CONTROLLER_TIMEOUT);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_ERROR);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"boot-2\",\"session_id\":4,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[],\"summary\":\"Tarde.\"}", 120032)
        == NEKO_CONTROLLER_STALE);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_ERROR);
}

static void test_pause_resume_double_touch_and_retry(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 1) == NEKO_CONTROLLER_COMMAND_PENDING);
    assert(io.line_count == 1);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":9,"
        "\"state\":\"recording\",\"is_demo\":true}", 2) == NEKO_CONTROLLER_OK);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_PAUSE, 3) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_PAUSE, 4) == NEKO_CONTROLLER_COMMAND_PENDING);
    assert(io.line_count == 2);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":9,"
        "\"state\":\"paused\",\"is_demo\":true}", 5) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_PAUSED);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_RESUME, 6) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-3\",\"session_id\":9,"
        "\"state\":\"recording\",\"is_demo\":true}", 7) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_RECORDING);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_FINISH, 8) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"error\",\"request_id\":\"boot-4\",\"session_id\":9,"
        "\"state\":\"error\",\"code\":\"capture_failed\",\"message\":\"captura indisponivel\"}", 9)
        == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_ERROR);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_RETRY, 10) == NEKO_CONTROLLER_OK);
    assert(io.line_count == 5);
    assert(strstr(io.lines[4], "\"command\":\"retry\"") != NULL);
    assert(strstr(io.lines[4], "\"session_id\":9") != NULL);
}

static void test_request_ids_include_boot_nonce_and_resend_preserves_request(void)
{
    neko_controller_t first;
    neko_controller_t second;
    fake_io_t io1;
    fake_io_t io2;

    init_controller_with_nonce(&first, &io1, "bootA");
    init_controller_with_nonce(&second, &io2, "bootB");
    assert(neko_controller_touch(&first, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&second, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(strstr(io1.lines[0], "\"request_id\":\"bootA-1\"") != NULL);
    assert(strstr(io2.lines[0], "\"request_id\":\"bootB-1\"") != NULL);

    assert(neko_controller_touch(&first, NEKO_TOUCH_RESEND, 2000) == NEKO_CONTROLLER_OK);
    assert(io1.line_count == 2);
    assert(strcmp(io1.lines[0], io1.lines[1]) == 0);
    assert(neko_controller_tick(&first, 6001) == NEKO_CONTROLLER_OK);
    assert(neko_controller_tick(&first, 7001) == NEKO_CONTROLLER_TIMEOUT);
    assert(neko_controller_touch(&first, NEKO_TOUCH_RESEND, 7100) == NEKO_CONTROLLER_OK);
    assert(io1.line_count == 3);
    assert(strcmp(io1.lines[0], io1.lines[2]) == 0);
}

static void test_heartbeat_does_not_replace_finish_result_request(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":10,"
        "\"state\":\"recording\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_FINISH, 20) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":10,"
        "\"state\":\"processing\",\"is_demo\":false}", 30) == NEKO_CONTROLLER_OK);
    assert(neko_controller_tick(&controller, 2031) == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[2], "\"command\":\"status\"") != NULL);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-3\",\"session_id\":10,"
        "\"state\":\"processing\",\"is_demo\":false}", 2040) == NEKO_CONTROLLER_OK);
    assert(neko_controller_tick(&controller, 8041) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_PROCESSING);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"boot-2\",\"session_id\":10,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[],\"summary\":\"Final.\"}", 9000)
        == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_SUCCESS);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"error\",\"request_id\":\"boot-2\",\"session_id\":10,"
        "\"state\":\"error\",\"code\":\"late\",\"message\":\"erro tardio\"}", 9010)
        == NEKO_CONTROLLER_STALE);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_SUCCESS);
}

static void test_voice_events_do_not_starve_status_heartbeat(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":11,"
        "\"state\":\"recording\",\"is_demo\":true}", 10) == NEKO_CONTROLLER_OK);
    for (uint32_t t = 210; t < 2010; t += 200) {
        assert(neko_controller_receive(&controller,
            "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":11,"
            "\"state\":\"recording\",\"is_demo\":true,"
            "\"voice\":{\"level\":30,\"clipping\":false,\"quality\":\"ok\"}}", t)
            == NEKO_CONTROLLER_OK);
        assert(neko_controller_tick(&controller, t) == NEKO_CONTROLLER_OK);
    }
    assert(neko_controller_tick(&controller, 2010) == NEKO_CONTROLLER_OK);
    assert(io.line_count == 2);
    assert(strstr(io.lines[1], "\"command\":\"status\"") != NULL);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":11,"
        "\"state\":\"recording\",\"is_demo\":true}", 2020) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_RECORDING);
}

static void test_retry_accepts_new_session_and_direct_result(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":9,"
        "\"state\":\"recording\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"error\",\"request_id\":\"boot-2\",\"session_id\":9,"
        "\"state\":\"error\",\"code\":\"capture_failed\",\"message\":\"falha\"}", 20)
        == NEKO_CONTROLLER_STALE);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_FINISH, 30) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"error\",\"request_id\":\"boot-2\",\"session_id\":9,"
        "\"state\":\"error\",\"code\":\"capture_failed\",\"message\":\"falha\"}", 40)
        == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_RETRY, 50) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-3\",\"session_id\":11,"
        "\"state\":\"recording\",\"is_demo\":false}", 60) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_RECORDING);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_FINISH, 70) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"boot-4\",\"session_id\":11,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[],\"summary\":\"Direto.\"}", 80)
        == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_SUCCESS);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_RETRY, 90) == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[4], "\"session_id\":11") != NULL);
}

static void test_null_session_idle_and_start_error_are_not_parser_failures(void)
{
    neko_controller_t controller;
    fake_io_t io;
    neko_mac_message_t message;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_STATUS, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":null,"
        "\"state\":\"idle\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_IDLE);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 20) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"error\",\"request_id\":\"boot-2\",\"session_id\":null,"
        "\"state\":\"error\",\"code\":\"backend_unavailable\","
        "\"message\":\"backend indisponivel\"}", 30) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_ERROR);

    assert(neko_protocol_parse_mac_line(
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"rid\",\"session_id\":null,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[],\"summary\":\"Nao.\"}",
        &message) == NEKO_PROTOCOL_ERR_INVALID_FIELD);
}

static void test_pending_command_rejects_unexpected_state_ack(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":20,"
        "\"state\":\"recording\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_PAUSE, 20) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":20,"
        "\"state\":\"recording\",\"is_demo\":false}", 30)
        == NEKO_CONTROLLER_INVALID_MESSAGE);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_ERROR);
}

static void test_heartbeat_result_can_recover_processing_session(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":21,"
        "\"state\":\"recording\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_FINISH, 20) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":21,"
        "\"state\":\"processing\",\"is_demo\":false}", 30) == NEKO_CONTROLLER_OK);
    assert(neko_controller_tick(&controller, 2031) == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[2], "\"request_id\":\"boot-3\"") != NULL);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"boot-3\",\"session_id\":21,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[],\"summary\":\"Recuperado.\"}", 2040)
        == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_SUCCESS);
    assert(strcmp(neko_controller_summary(&controller), "Recuperado.") == 0);
}

static void test_delayed_error_and_wrapsafe_time_do_not_break_session(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0xFFFFFF00U)
        == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":12,"
        "\"state\":\"recording\",\"is_demo\":false}", 0xFFFFFF10U) == NEKO_CONTROLLER_OK);
    assert(neko_controller_tick(&controller, 0x00000020U) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_RECORDING);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"error\",\"request_id\":\"old\",\"session_id\":12,"
        "\"state\":\"error\",\"code\":\"old\",\"message\":\"erro antigo\"}", 0x00000030U)
        == NEKO_CONTROLLER_STALE);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_RECORDING);
}

static void test_protocol_rejects_malformed_content(void)
{
    neko_mac_message_t message;

    assert(neko_protocol_parse_mac_line(
        "{\"v\":1,\"type\":\"result\",\"type\":\"state\",\"request_id\":\"req-1\"}",
        &message) == NEKO_PROTOCOL_ERR_DUPLICATE_KEY);

    assert(neko_protocol_parse_mac_line(
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"req-1\",\"session_id\":1,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[1],\"summary\":\"ok\"}",
        &message) == NEKO_PROTOCOL_ERR_INVALID_FIELD);

    assert(neko_protocol_parse_mac_line(
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"bad space\",\"session_id\":1,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[],\"summary\":\"ok\"}",
        &message) == NEKO_PROTOCOL_ERR_INVALID_FIELD);

    assert(neko_protocol_parse_mac_line(
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"req-1\",\"session_id\":1,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[],\"summary\":\"ok\"}",
        &message) == NEKO_PROTOCOL_OK);
    assert(message.kind == NEKO_MAC_RESULT);
    assert(message.topic_count == 0);

    assert(neko_protocol_parse_mac_line(
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"req-1\",\"session_id\":1,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[\"rea\\u00e7ao\"],"
        "\"summary\":\"sess\\u00e3o ok\"}",
        &message) == NEKO_PROTOCOL_OK);
    assert(strcmp(message.topics[0], "rea?ao") == 0);
}

static void test_diagnose_ready_recovery_and_recovery_commands(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, (neko_touch_event_t)8, 0)
        == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[0], "\"command\":\"diagnose\"") != NULL);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":null,"
        "\"state\":\"checking\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(strcmp(neko_controller_state_name(neko_controller_state(&controller)),
                  "CHECKING") == 0);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":null,"
        "\"state\":\"ready\",\"is_demo\":false}", 20) == NEKO_CONTROLLER_OK);
    assert(strcmp(neko_controller_state_name(neko_controller_state(&controller)),
                  "READY") == 0);

    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":44,"
        "\"state\":\"recovery\",\"is_demo\":false}", 30) == NEKO_CONTROLLER_OK);
    assert(strcmp(neko_controller_state_name(neko_controller_state(&controller)),
                  "RECOVERY") == 0);

    assert(neko_controller_touch(&controller, (neko_touch_event_t)10, 40)
        == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[1], "\"command\":\"recover\"") != NULL);
    assert(strstr(io.lines[1], "\"session_id\":44") != NULL);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":44,"
        "\"state\":\"ready\",\"is_demo\":false}", 50) == NEKO_CONTROLLER_OK);
    assert(strcmp(neko_controller_state_name(neko_controller_state(&controller)),
                  "READY") == 0);
}

static void test_control_commands_cancel_discard_reset_and_calibrate_order(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, (neko_touch_event_t)9, 0)
        == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[0], "\"command\":\"calibrate\"") != NULL);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":null,"
        "\"state\":\"ready\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(strcmp(neko_controller_state_name(neko_controller_state(&controller)),
                  "READY") == 0);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 20) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":77,"
        "\"state\":\"recording\",\"is_demo\":false}", 30) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, (neko_touch_event_t)12, 40)
        == NEKO_CONTROLLER_OK);
    assert(io.line_count == 2);
    assert(neko_controller_touch(&controller, (neko_touch_event_t)12, 300)
        == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[2], "\"command\":\"cancel\"") != NULL);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-3\",\"session_id\":77,"
        "\"state\":\"idle\",\"is_demo\":false}", 310) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_IDLE);

    assert(neko_controller_touch(&controller, (neko_touch_event_t)11, 320)
        == NEKO_CONTROLLER_INVALID_STATE);
    assert(neko_controller_touch(&controller, (neko_touch_event_t)13, 330)
        == NEKO_CONTROLLER_OK);
    assert(io.line_count == 3);
    assert(neko_controller_touch(&controller, (neko_touch_event_t)13, 590)
        == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[3], "\"command\":\"reset\"") != NULL);
}

static void test_result_optional_duration_trend_and_processing_progress(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":88,"
        "\"state\":\"recording\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_FINISH, 20) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-2\",\"session_id\":88,"
        "\"state\":\"processing\",\"is_demo\":false,"
        "\"journey\":{\"step\":\"topics\",\"status\":\"running\",\"duration_ms\":119000}}",
        119000) == NEKO_CONTROLLER_OK);
    assert(neko_controller_tick(&controller, 121000) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_PROCESSING);

    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"boot-2\",\"session_id\":88,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[\"energia\"],"
        "\"summary\":\"Explicacao organizada.\",\"duration_seconds\":73,"
        "\"subject\":\"Fisica\",\"trend_text\":\"Mais claro que a sessao anterior\"}",
        122000) == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_SUCCESS);
    assert(io.durations[io.render_count - 1] == 73);
    assert(strcmp(io.trends[io.render_count - 1],
                  "Mais claro que a sessao anterior") == 0);
}

static void assert_hit_target(const neko_layout_rect_t *rect)
{
    assert(rect->width >= 44);
    assert(rect->height >= 44);
}

static void test_portable_touch_layout_faces_cards_and_targets(void)
{
    const char topics[2][NEKO_TOPIC_MAX + 1] = {"Topico A", "Topico B"};
    neko_controller_view_t view = {
        .message = "sessao concluida",
        .summary = "Resumo curto",
        .topics = topics,
        .topic_count = 2,
        .is_demo = false,
        .duration_seconds = 73,
        .subject = "Fisica",
        .trend_text = "Mais claro que a sessao anterior",
    };
    neko_layout_model_t portrait;
    neko_layout_model_t landscape;

    assert(neko_layout_build(NEKO_CONTROLLER_SUCCESS, &view, 240, 320,
                             false, 0, &portrait));
    assert(portrait.face.width >= 92);
    assert(portrait.face.height >= 92);
    assert(portrait.face.height > portrait.primary_action.height);
    assert(portrait.card_count == 4);
    assert(portrait.reduced_motion == false);
    assert_hit_target(&portrait.primary_action);
    assert_hit_target(&portrait.next_action);

    assert(neko_layout_build(NEKO_CONTROLLER_SUCCESS, &view, 320, 240,
                             true, 3, &landscape));
    assert(landscape.face.width >= 120);
    assert(landscape.face.height >= 120);
    assert(landscape.card_index == 3);
    assert(landscape.reduced_motion == true);
    assert_hit_target(&landscape.primary_action);
}

static bool scene_has_op(const neko_scene_t *scene, neko_scene_op_kind_t kind)
{
    size_t i;
    for (i = 0; i < scene->op_count; i++) {
        if (scene->ops[i].kind == kind) {
            return true;
        }
    }
    return false;
}

static bool scene_has_text(const neko_scene_t *scene, const char *text)
{
    size_t i;
    for (i = 0; i < scene->op_count; i++) {
        if ((scene->ops[i].kind == NEKO_SCENE_OP_TEXT
             || scene->ops[i].kind == NEKO_SCENE_OP_BUTTON
             || scene->ops[i].kind == NEKO_SCENE_OP_FACE)
            && strcmp(scene->ops[i].text, text) == 0) {
            return true;
        }
    }
    return false;
}

static const neko_scene_op_t *first_op(const neko_scene_t *scene,
                                       neko_scene_op_kind_t kind)
{
    size_t i;
    for (i = 0; i < scene->op_count; i++) {
        if (scene->ops[i].kind == kind) {
            return &scene->ops[i];
        }
    }
    return NULL;
}

static void assert_rect_in_bounds(const neko_layout_rect_t *rect, int width, int height)
{
    assert(rect->x >= 0);
    assert(rect->y >= 0);
    assert(rect->width > 0);
    assert(rect->height > 0);
    assert(rect->x + rect->width <= width);
    assert(rect->y + rect->height <= height);
}

static bool rects_overlap(const neko_layout_rect_t *a, const neko_layout_rect_t *b)
{
    return a->x < b->x + b->width
        && a->x + a->width > b->x
        && a->y < b->y + b->height
        && a->y + a->height > b->y;
}

static bool important_op(neko_scene_op_kind_t kind)
{
    return kind == NEKO_SCENE_OP_FACE
        || kind == NEKO_SCENE_OP_TEXT
        || kind == NEKO_SCENE_OP_BUTTON;
}

static void assert_layout_safe_for_state(neko_controller_state_t state)
{
    neko_controller_view_t view = {
        .message = "estado",
        .summary = "Resumo curto",
        .topic_count = 8,
        .is_demo = false,
        .duration_seconds = 91,
        .trend_text = "Evolucao disponivel",
    };
    neko_layout_model_t layout;
    neko_scene_t scene;
    size_t i;

    assert(neko_layout_build(state, &view, 240, 320, false, 0, &layout));
    assert_rect_in_bounds(&layout.face, 240, 320);
    for (i = 0; i < layout.hit_count; i++) {
        assert_rect_in_bounds(&layout.hits[i].rect, 240, 320);
        assert_hit_target(&layout.hits[i].rect);
        assert(!rects_overlap(&layout.face, &layout.hits[i].rect));
    }
    assert(neko_scene_build(state, &view, &layout, &scene));
    assert(scene_has_op(&scene, NEKO_SCENE_OP_FACE));
    assert(scene_has_op(&scene, NEKO_SCENE_OP_TEXT));
    assert(scene_has_op(&scene, NEKO_SCENE_OP_BUTTON));
}

static void assert_scene_no_important_overlap(const neko_scene_t *scene)
{
    size_t i;
    size_t j;
    for (i = 0; i < scene->op_count; i++) {
        for (j = i + 1; j < scene->op_count; j++) {
            if (important_op(scene->ops[i].kind)
                && important_op(scene->ops[j].kind)) {
                assert(!rects_overlap(&scene->ops[i].rect, &scene->ops[j].rect));
            }
        }
    }
}

static void test_scene_result_content_badges_and_grouped_topics(void)
{
    const char topics[3][NEKO_TOPIC_MAX + 1] = {
        "Azul",
        "Preto",
        "Rosa",
    };
    neko_controller_view_t view = {
        .message = "sessao concluida",
        .summary = "Resumo curto da explicacao",
        .topics = topics,
        .topic_count = 3,
        .is_demo = true,
        .duration_seconds = 73,
        .trend_text = "Mais claro",
    };
    neko_layout_model_t layout;
    neko_scene_t scene;

    assert(neko_layout_build(NEKO_CONTROLLER_SUCCESS, &view, 240, 320,
                             false, 0, &layout));
    assert(layout.card_count == 4);
    assert(neko_scene_build(NEKO_CONTROLLER_SUCCESS, &view, &layout, &scene));
    assert(scene_has_text(&scene, "DEMO"));
    assert(scene_has_text(&scene, "Resumo curto da explicacao"));

    assert(neko_layout_build(NEKO_CONTROLLER_SUCCESS, &view, 240, 320,
                             false, 1, &layout));
    assert(neko_scene_build(NEKO_CONTROLLER_SUCCESS, &view, &layout, &scene));
    assert(scene_has_text(&scene, "Azul / Preto / Rosa"));

    assert(neko_layout_build(NEKO_CONTROLLER_SUCCESS, &view, 240, 320,
                             false, 2, &layout));
    assert(neko_scene_build(NEKO_CONTROLLER_SUCCESS, &view, &layout, &scene));
    assert(scene_has_text(&scene, "73s"));

    assert(neko_layout_build(NEKO_CONTROLLER_SUCCESS, &view, 240, 320,
                             false, 3, &layout));
    assert(neko_scene_build(NEKO_CONTROLLER_SUCCESS, &view, &layout, &scene));
    assert(scene_has_text(&scene, "Mais claro"));
}

static void test_scene_confirmation_badge_face_expression_and_overlap_both_orientations(void)
{
    neko_controller_view_t view = {
        .message = "confirmar acao",
        .summary = "Resumo",
        .topic_count = 1,
        .is_demo = false,
        .voice_level = 80,
        .voice_clipping = true,
        .voice_quality = NEKO_VOICE_QUALITY_CLIPPING,
    };
    neko_layout_model_t portrait;
    neko_layout_model_t landscape;
    neko_scene_t scene_a;
    neko_scene_t scene_b;
    const neko_scene_op_t *face_a;
    const neko_scene_op_t *face_b;

    assert(neko_layout_build(NEKO_CONTROLLER_RECORDING, &view, 240, 320,
                             false, 0, &portrait));
    assert(neko_scene_build(NEKO_CONTROLLER_RECORDING, &view, &portrait, &scene_a));
    assert(scene_has_text(&scene_a, "REAL"));
    assert(scene_has_text(&scene_a, "confirmar acao"));
    assert_scene_no_important_overlap(&scene_a);
    face_a = first_op(&scene_a, NEKO_SCENE_OP_FACE);
    assert(face_a != NULL);

    assert(neko_layout_build(NEKO_CONTROLLER_RECORDING, &view, 320, 240,
                             false, 0, &landscape));
    assert(neko_scene_build(NEKO_CONTROLLER_RECORDING, &view, &landscape, &scene_b));
    assert_scene_no_important_overlap(&scene_b);

    view.voice_level = 0;
    view.voice_clipping = false;
    view.voice_quality = NEKO_VOICE_QUALITY_UNKNOWN;
    assert(neko_scene_build(NEKO_CONTROLLER_PAUSED, &view, &portrait, &scene_b));
    face_b = first_op(&scene_b, NEKO_SCENE_OP_FACE);
    assert(face_b != NULL);
    assert(strcmp(face_a->text, face_b->text) != 0);

    assert(neko_layout_build(NEKO_CONTROLLER_RECORDING, &view, 240, 320,
                             true, 0, &portrait));
    assert(neko_scene_build(NEKO_CONTROLLER_RECORDING, &view, &portrait, &scene_b));
    face_b = first_op(&scene_b, NEKO_SCENE_OP_FACE);
    assert(face_b != NULL);
    assert(strstr(face_b->text, "static") != NULL);
}

static void assert_hit_event(neko_controller_state_t state,
                             neko_touch_event_t event,
                             bool enabled)
{
    neko_controller_view_t view = {
        .message = "estado",
        .summary = "Resumo curto",
        .topic_count = 2,
        .is_demo = false,
        .duration_seconds = 10,
        .trend_text = "Evolucao",
    };
    neko_layout_model_t layout;
    neko_touch_event_t out_event = NEKO_TOUCH_STATUS;
    bool out_enabled = true;
    size_t i;

    assert(neko_layout_build(state, &view, 240, 320, false, 0, &layout));
    for (i = 0; i < layout.hit_count; i++) {
        if (layout.hits[i].event == event) {
            int x = layout.hits[i].rect.x + 1;
            int y = layout.hits[i].rect.y + 1;
            assert(neko_layout_hit_test(&layout, x, y, &out_event, &out_enabled));
            assert(out_event == event);
            assert(out_enabled == enabled);
            return;
        }
    }
    assert(false);
}

static void assert_no_hit_event(neko_controller_state_t state,
                                neko_touch_event_t event)
{
    neko_controller_view_t view = {
        .message = "estado",
        .summary = "Resumo curto",
        .topic_count = 2,
        .is_demo = false,
    };
    neko_layout_model_t layout;
    size_t i;

    assert(neko_layout_build(state, &view, 240, 320, false, 0, &layout));
    for (i = 0; i < layout.hit_count; i++) {
        assert(layout.hits[i].event != event);
    }
}

static void test_scene_hit_actions_for_core_states(void)
{
    assert_layout_safe_for_state(NEKO_CONTROLLER_IDLE);
    assert_layout_safe_for_state(NEKO_CONTROLLER_CHECKING);
    assert_layout_safe_for_state(NEKO_CONTROLLER_READY);
    assert_layout_safe_for_state(NEKO_CONTROLLER_RECORDING);
    assert_layout_safe_for_state(NEKO_CONTROLLER_PAUSED);
    assert_layout_safe_for_state(NEKO_CONTROLLER_PROCESSING);
    assert_layout_safe_for_state(NEKO_CONTROLLER_SUCCESS);
    assert_layout_safe_for_state(NEKO_CONTROLLER_ERROR);
    assert_layout_safe_for_state(NEKO_CONTROLLER_RECOVERY);

    assert_no_hit_event(NEKO_CONTROLLER_IDLE, NEKO_TOUCH_START);
    assert_hit_event(NEKO_CONTROLLER_IDLE, NEKO_TOUCH_DIAGNOSE, true);
    assert_hit_event(NEKO_CONTROLLER_IDLE, NEKO_TOUCH_RESET, true);
    assert_hit_event(NEKO_CONTROLLER_READY, NEKO_TOUCH_START, true);
    assert_hit_event(NEKO_CONTROLLER_READY, NEKO_TOUCH_CALIBRATE, true);
    assert_hit_event(NEKO_CONTROLLER_READY, NEKO_TOUCH_DIAGNOSE, true);
    assert_hit_event(NEKO_CONTROLLER_RECORDING, NEKO_TOUCH_PAUSE, true);
    assert_hit_event(NEKO_CONTROLLER_RECORDING, NEKO_TOUCH_FINISH, true);
    assert_hit_event(NEKO_CONTROLLER_RECORDING, NEKO_TOUCH_CANCEL, true);
    assert_hit_event(NEKO_CONTROLLER_PAUSED, NEKO_TOUCH_RESUME, true);
    assert_hit_event(NEKO_CONTROLLER_PAUSED, NEKO_TOUCH_FINISH, true);
    assert_hit_event(NEKO_CONTROLLER_PAUSED, NEKO_TOUCH_CANCEL, true);
    assert_hit_event(NEKO_CONTROLLER_PROCESSING, NEKO_TOUCH_STATUS, true);
    assert_hit_event(NEKO_CONTROLLER_PROCESSING, NEKO_TOUCH_CANCEL, true);
    assert_hit_event(NEKO_CONTROLLER_SUCCESS, NEKO_TOUCH_PREV_CARD, true);
    assert_hit_event(NEKO_CONTROLLER_SUCCESS, NEKO_TOUCH_NEXT_CARD, true);
    assert_hit_event(NEKO_CONTROLLER_SUCCESS, NEKO_TOUCH_RETRY, true);
    assert_hit_event(NEKO_CONTROLLER_SUCCESS, NEKO_TOUCH_RESET, true);
    assert_hit_event(NEKO_CONTROLLER_ERROR, NEKO_TOUCH_RETRY, true);
    assert_hit_event(NEKO_CONTROLLER_ERROR, NEKO_TOUCH_DIAGNOSE, true);
    assert_hit_event(NEKO_CONTROLLER_ERROR, NEKO_TOUCH_RESET, true);
    assert_hit_event(NEKO_CONTROLLER_RECOVERY, NEKO_TOUCH_RECOVER, true);
    assert_hit_event(NEKO_CONTROLLER_RECOVERY, NEKO_TOUCH_DISCARD, true);
    assert_hit_event(NEKO_CONTROLLER_RECOVERY, NEKO_TOUCH_CANCEL, true);
}

static void test_local_theme_button_across_session_states(void)
{
    neko_controller_view_t view = {.message = "Pronto", .is_demo = false};
    for (int state = NEKO_CONTROLLER_IDLE; state <= NEKO_CONTROLLER_ERROR; state++) {
        neko_layout_model_t layout;
        neko_scene_t scene;
        neko_touch_event_t event = 0;
        bool enabled = false;
        assert(neko_layout_build((neko_controller_state_t)state, &view,
                                 240, 320, false, 0, &layout));
        assert(layout.hits[0].event == NEKO_TOUCH_THEME);
        assert(layout.hits[0].rect.width >= NEKO_LAYOUT_HIT_TARGET_MIN);
        assert(layout.hits[0].rect.height >= NEKO_LAYOUT_HIT_TARGET_MIN);
        assert(neko_layout_hit_test(&layout, 190, 20, &event, &enabled));
        assert(event == NEKO_TOUCH_THEME && enabled);
        assert(!layout.dark_theme);
        assert(strcmp(layout.hits[0].label, "ESCURO") == 0);
        neko_layout_set_theme(&layout, true);
        assert(strcmp(layout.hits[0].label, "CLARO") == 0);
        assert(neko_scene_build((neko_controller_state_t)state, &view,
                                &layout, &scene));
        assert(scene.dark_theme && scene_has_text(&scene, "CLARO"));
        assert_scene_no_important_overlap(&scene);
        neko_layout_set_theme(&layout, false);
        assert(neko_scene_build((neko_controller_state_t)state, &view,
                                &layout, &scene));
        assert(!scene.dark_theme && scene_has_text(&scene, "ESCURO"));
    }
}

static void test_result_card_navigation_updates_view_only(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_START, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":33,"
        "\"state\":\"recording\",\"is_demo\":false}", 10) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_FINISH, 20) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"result\",\"request_id\":\"boot-2\",\"session_id\":33,"
        "\"state\":\"completed\",\"is_demo\":false,\"asr_provider\":\"faster-whisper\","
        "\"topic_provider\":\"local\",\"topics\":[\"a\",\"b\",\"c\"],"
        "\"summary\":\"Ok\",\"duration_seconds\":12,\"trend_text\":\"Melhor\"}",
        30) == NEKO_CONTROLLER_OK);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_NEXT_CARD, 40) == NEKO_CONTROLLER_OK);
    assert(io.card_indices[io.render_count - 1] == 1);
    assert(io.line_count == 2);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_PREV_CARD, 300) == NEKO_CONTROLLER_OK);
    assert(io.card_indices[io.render_count - 1] == 0);
    assert(io.line_count == 2);
}

static void test_recovery_discard_confirmation_and_async_diagnose_ready(void)
{
    neko_controller_t controller;
    fake_io_t io;
    init_controller(&controller, &io);

    assert(neko_controller_touch(&controller, NEKO_TOUCH_DIAGNOSE, 0) == NEKO_CONTROLLER_OK);
    assert(strstr(io.lines[0], "\"command\":\"diagnose\"") != NULL);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":55,"
        "\"state\":\"recovery\",\"is_demo\":false,"
        "\"diagnostic\":{\"component\":\"backend\",\"status\":\"ready\"}}", 20)
        == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_RECOVERY);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_DISCARD, 300) == NEKO_CONTROLLER_OK);
    assert(io.line_count == 1);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_DISCARD, 560) == NEKO_CONTROLLER_OK);
    assert(io.line_count == 2);
    assert(strstr(io.lines[1], "\"command\":\"discard\"") != NULL);

    init_controller(&controller, &io);
    assert(neko_controller_touch(&controller, NEKO_TOUCH_DIAGNOSE, 0) == NEKO_CONTROLLER_OK);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":null,"
        "\"state\":\"checking\",\"is_demo\":false,"
        "\"diagnostic\":{\"component\":\"microphone\",\"status\":\"pending\"}}", 20)
        == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_CHECKING);
    assert(neko_controller_receive(&controller,
        "{\"v\":1,\"type\":\"state\",\"request_id\":\"boot-1\",\"session_id\":null,"
        "\"state\":\"ready\",\"is_demo\":false,"
        "\"diagnostic\":{\"component\":\"microphone\",\"status\":\"ready\"}}", 400)
        == NEKO_CONTROLLER_OK);
    assert(neko_controller_state(&controller) == NEKO_CONTROLLER_READY);
}

static void test_touch_edge_requires_release_before_second_confirm(void)
{
    neko_touch_edge_t edge;
    neko_touch_edge_init(&edge);

    assert(neko_touch_edge_update(&edge, true, 10));
    assert(!neko_touch_edge_update(&edge, true, 60));
    assert(!neko_touch_edge_update(&edge, true, 110));
    assert(!neko_touch_edge_update(&edge, false, 160));
    assert(neko_touch_edge_update(&edge, true, 220));
}

int main(void)
{
    test_valid_completion_requires_correlated_result();
    test_invalid_stale_and_wrong_session_results_do_not_succeed();
    test_pending_timeout_processing_timeout_and_late_result();
    test_pause_resume_double_touch_and_retry();
    test_request_ids_include_boot_nonce_and_resend_preserves_request();
    test_heartbeat_does_not_replace_finish_result_request();
    test_voice_events_do_not_starve_status_heartbeat();
    test_retry_accepts_new_session_and_direct_result();
    test_null_session_idle_and_start_error_are_not_parser_failures();
    test_pending_command_rejects_unexpected_state_ack();
    test_heartbeat_result_can_recover_processing_session();
    test_delayed_error_and_wrapsafe_time_do_not_break_session();
    test_protocol_rejects_malformed_content();
    test_diagnose_ready_recovery_and_recovery_commands();
    test_control_commands_cancel_discard_reset_and_calibrate_order();
    test_result_optional_duration_trend_and_processing_progress();
    test_portable_touch_layout_faces_cards_and_targets();
    test_scene_hit_actions_for_core_states();
    test_local_theme_button_across_session_states();
    test_result_card_navigation_updates_view_only();
    test_recovery_discard_confirmation_and_async_diagnose_ready();
    test_scene_result_content_badges_and_grouped_topics();
    test_scene_confirmation_badge_face_expression_and_overlap_both_orientations();
    test_touch_edge_requires_release_before_second_confirm();
    puts("firmware controller tests passed");
    return 0;
}
