#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../main/neko_controller.h"
#include "../main/neko_protocol.h"

typedef struct {
    char lines[16][512];
    int line_count;
    neko_controller_state_t rendered[32];
    char summaries[32][NEKO_RESULT_SUMMARY_MAX + 1];
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

int main(void)
{
    test_valid_completion_requires_correlated_result();
    test_invalid_stale_and_wrong_session_results_do_not_succeed();
    test_pending_timeout_processing_timeout_and_late_result();
    test_pause_resume_double_touch_and_retry();
    test_request_ids_include_boot_nonce_and_resend_preserves_request();
    test_heartbeat_does_not_replace_finish_result_request();
    test_retry_accepts_new_session_and_direct_result();
    test_null_session_idle_and_start_error_are_not_parser_failures();
    test_pending_command_rejects_unexpected_state_ack();
    test_heartbeat_result_can_recover_processing_session();
    test_delayed_error_and_wrapsafe_time_do_not_break_session();
    test_protocol_rejects_malformed_content();
    puts("firmware controller tests passed");
    return 0;
}
