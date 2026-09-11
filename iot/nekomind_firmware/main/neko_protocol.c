#include "neko_protocol.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    const char *name;
    bool seen;
} key_seen_t;

static void skip_ws(const char **p)
{
    while (**p == ' ' || **p == '\t' || **p == '\r' || **p == '\n') {
        (*p)++;
    }
}

static bool parse_literal(const char **p, const char *literal)
{
    size_t len = strlen(literal);
    if (strncmp(*p, literal, len) != 0) {
        return false;
    }
    *p += len;
    return true;
}

static int hex_value(char ch)
{
    if (ch >= '0' && ch <= '9') {
        return ch - '0';
    }
    if (ch >= 'a' && ch <= 'f') {
        return ch - 'a' + 10;
    }
    if (ch >= 'A' && ch <= 'F') {
        return ch - 'A' + 10;
    }
    return -1;
}

static bool parse_json_string(const char **p, char *out, size_t out_size,
                              bool *truncated)
{
    size_t n = 0;
    if (**p != '"' || out_size == 0) {
        return false;
    }
    (*p)++;
    while (**p != '\0' && **p != '"') {
        unsigned char ch = (unsigned char)**p;
        if (ch < 0x20) {
            return false;
        }
        if (**p == '\\') {
            (*p)++;
            switch (**p) {
            case '"':
            case '\\':
            case '/':
                ch = (unsigned char)**p;
                break;
            case 'b':
                ch = '\b';
                break;
            case 'f':
                ch = '\f';
                break;
            case 'n':
                ch = '\n';
                break;
            case 'r':
                ch = '\r';
                break;
            case 't':
                ch = '\t';
                break;
            case 'u': {
                int h0;
                int h1;
                int h2;
                int h3;
                (*p)++;
                h0 = hex_value((*p)[0]);
                h1 = hex_value((*p)[1]);
                h2 = hex_value((*p)[2]);
                h3 = hex_value((*p)[3]);
                if (h0 < 0 || h1 < 0 || h2 < 0 || h3 < 0) {
                    return false;
                }
                {
                    int codepoint = (h0 << 12) | (h1 << 8) | (h2 << 4) | h3;
                    ch = (unsigned char)(codepoint < 0x80 ? codepoint : '?');
                }
                *p += 3;
                break;
            }
            default:
                return false;
            }
        }
        if (n + 1 < out_size) {
            out[n++] = (char)ch;
        } else if (truncated != NULL) {
            *truncated = true;
        }
        (*p)++;
    }
    if (**p != '"') {
        return false;
    }
    (*p)++;
    out[n] = '\0';
    return true;
}

static bool parse_int_value(const char **p, int *out)
{
    char *end = NULL;
    long value;
    if (!isdigit((unsigned char)**p)) {
        return false;
    }
    value = strtol(*p, &end, 10);
    if (end == *p || value <= 0 || value > 2147483647L) {
        return false;
    }
    *out = (int)value;
    *p = end;
    return true;
}

static bool parse_nonnegative_int_value(const char **p, int *out)
{
    char *end = NULL;
    long value;
    if (!isdigit((unsigned char)**p)) {
        return false;
    }
    value = strtol(*p, &end, 10);
    if (end == *p || value < 0 || value > 2147483647L) {
        return false;
    }
    *out = (int)value;
    *p = end;
    return true;
}

static bool parse_bool_value(const char **p, bool *out)
{
    if (parse_literal(p, "true")) {
        *out = true;
        return true;
    }
    if (parse_literal(p, "false")) {
        *out = false;
        return true;
    }
    return false;
}

static bool skip_json_value(const char **p);

static bool skip_json_object(const char **p)
{
    if (**p != '{') {
        return false;
    }
    (*p)++;
    skip_ws(p);
    if (**p == '}') {
        (*p)++;
        return true;
    }
    while (**p != '\0') {
        char key[32] = {0};
        bool truncated = false;
        if (!parse_json_string(p, key, sizeof(key), &truncated) || truncated) {
            return false;
        }
        skip_ws(p);
        if (**p != ':') {
            return false;
        }
        (*p)++;
        skip_ws(p);
        if (!skip_json_value(p)) {
            return false;
        }
        skip_ws(p);
        if (**p == '}') {
            (*p)++;
            return true;
        }
        if (**p != ',') {
            return false;
        }
        (*p)++;
        skip_ws(p);
    }
    return false;
}

static bool skip_json_array(const char **p)
{
    if (**p != '[') {
        return false;
    }
    (*p)++;
    skip_ws(p);
    if (**p == ']') {
        (*p)++;
        return true;
    }
    while (**p != '\0') {
        if (!skip_json_value(p)) {
            return false;
        }
        skip_ws(p);
        if (**p == ']') {
            (*p)++;
            return true;
        }
        if (**p != ',') {
            return false;
        }
        (*p)++;
        skip_ws(p);
    }
    return false;
}

static bool skip_json_number(const char **p)
{
    char *end = NULL;
    (void)strtod(*p, &end);
    if (end == *p) {
        return false;
    }
    *p = end;
    return true;
}

static bool skip_json_value(const char **p)
{
    char scratch[8] = {0};
    bool truncated = false;
    skip_ws(p);
    if (**p == '"') {
        return parse_json_string(p, scratch, sizeof(scratch), &truncated);
    }
    if (**p == '{') {
        return skip_json_object(p);
    }
    if (**p == '[') {
        return skip_json_array(p);
    }
    if (**p == '-' || isdigit((unsigned char)**p)) {
        return skip_json_number(p);
    }
    return parse_literal(p, "true")
        || parse_literal(p, "false")
        || parse_literal(p, "null");
}

static bool parse_topics(const char **p, neko_mac_message_t *out,
                         bool *invalid_field)
{
    if (**p != '[') {
        return false;
    }
    (*p)++;
    skip_ws(p);
    out->topic_count = 0;
    if (**p == ']') {
        (*p)++;
        return true;
    }
    while (**p != '\0') {
        bool truncated = false;
        if (out->topic_count >= NEKO_TOPIC_COUNT_MAX) {
            *invalid_field = true;
            return false;
        }
        if (!parse_json_string(p, out->topics[out->topic_count],
                               sizeof(out->topics[out->topic_count]),
                               &truncated)) {
            *invalid_field = true;
            return false;
        }
        if (truncated || out->topics[out->topic_count][0] == '\0') {
            *invalid_field = true;
            return false;
        }
        out->topic_count++;
        skip_ws(p);
        if (**p == ']') {
            (*p)++;
            return true;
        }
        if (**p != ',') {
            return false;
        }
        (*p)++;
        skip_ws(p);
    }
    return false;
}

static bool voice_quality_from_string(const char *text, neko_voice_quality_t *quality)
{
    if (strcmp(text, "unknown") == 0) {
        *quality = NEKO_VOICE_QUALITY_UNKNOWN;
    } else if (strcmp(text, "ok") == 0) {
        *quality = NEKO_VOICE_QUALITY_OK;
    } else if (strcmp(text, "low") == 0) {
        *quality = NEKO_VOICE_QUALITY_LOW;
    } else if (strcmp(text, "clipping") == 0) {
        *quality = NEKO_VOICE_QUALITY_CLIPPING;
    } else {
        return false;
    }
    return true;
}

static bool parse_voice(const char **p, neko_mac_message_t *out)
{
    bool saw_level = false;
    bool saw_clipping = false;
    bool saw_quality = false;
    if (**p != '{') {
        return false;
    }
    (*p)++;
    skip_ws(p);
    while (**p != '\0' && **p != '}') {
        char key[32] = {0};
        char scratch[16] = {0};
        bool truncated = false;
        if (!parse_json_string(p, key, sizeof(key), &truncated) || truncated) {
            return false;
        }
        skip_ws(p);
        if (**p != ':') {
            return false;
        }
        (*p)++;
        skip_ws(p);
        if (strcmp(key, "level") == 0) {
            if (!parse_nonnegative_int_value(p, &out->voice_level)
                || out->voice_level < 0 || out->voice_level > 100) {
                return false;
            }
            saw_level = true;
        } else if (strcmp(key, "clipping") == 0) {
            if (!parse_bool_value(p, &out->voice_clipping)) {
                return false;
            }
            saw_clipping = true;
        } else if (strcmp(key, "quality") == 0) {
            if (!parse_json_string(p, scratch, sizeof(scratch), &truncated)
                || truncated
                || !voice_quality_from_string(scratch, &out->voice_quality)) {
                return false;
            }
            saw_quality = true;
        } else {
            return false;
        }
        skip_ws(p);
        if (**p == ',') {
            (*p)++;
            skip_ws(p);
            continue;
        }
        if (**p != '}') {
            return false;
        }
    }
    if (**p != '}') {
        return false;
    }
    (*p)++;
    out->has_voice = saw_level && saw_clipping && saw_quality;
    return out->has_voice;
}

static bool parse_journey(const char **p, neko_mac_message_t *out)
{
    if (**p != '{') {
        return false;
    }
    (*p)++;
    skip_ws(p);
    while (**p != '\0' && **p != '}') {
        char key[32] = {0};
        bool truncated = false;
        if (!parse_json_string(p, key, sizeof(key), &truncated) || truncated) {
            return false;
        }
        skip_ws(p);
        if (**p != ':') {
            return false;
        }
        (*p)++;
        skip_ws(p);
        if (strcmp(key, "status") == 0) {
            if (!parse_json_string(p, out->journey_status,
                                   sizeof(out->journey_status), &truncated)
                || truncated) {
                return false;
            }
            if (strcmp(out->journey_status, "running") == 0
                || strcmp(out->journey_status, "waiting") == 0) {
                out->has_journey_progress = true;
            }
        } else if (strcmp(key, "step") == 0) {
            if (!parse_json_string(p, out->journey_step,
                                   sizeof(out->journey_step), &truncated)
                || truncated) {
                return false;
            }
        } else {
            if (!skip_json_value(p)) {
                return false;
            }
        }
        skip_ws(p);
        if (**p == ',') {
            (*p)++;
            skip_ws(p);
            continue;
        }
        if (**p != '}') {
            return false;
        }
    }
    if (**p != '}') {
        return false;
    }
    (*p)++;
    return true;
}

static bool parse_diagnostic(const char **p, neko_mac_message_t *out)
{
    if (**p != '{') {
        return false;
    }
    (*p)++;
    skip_ws(p);
    while (**p != '\0' && **p != '}') {
        char key[32] = {0};
        bool truncated = false;
        if (!parse_json_string(p, key, sizeof(key), &truncated) || truncated) {
            return false;
        }
        skip_ws(p);
        if (**p != ':') {
            return false;
        }
        (*p)++;
        skip_ws(p);
        if (strcmp(key, "component") == 0) {
            if (!parse_json_string(p, out->diagnostic_component,
                                   sizeof(out->diagnostic_component), &truncated)
                || truncated) {
                return false;
            }
        } else if (strcmp(key, "status") == 0) {
            if (!parse_json_string(p, out->diagnostic_status,
                                   sizeof(out->diagnostic_status), &truncated)
                || truncated) {
                return false;
            }
        } else {
            if (!skip_json_value(p)) {
                return false;
            }
        }
        skip_ws(p);
        if (**p == ',') {
            (*p)++;
            skip_ws(p);
            continue;
        }
        if (**p != '}') {
            return false;
        }
    }
    if (**p != '}') {
        return false;
    }
    (*p)++;
    return true;
}

static int key_index(const char *key, key_seen_t *keys, size_t count)
{
    size_t i;
    for (i = 0; i < count; i++) {
        if (strcmp(key, keys[i].name) == 0) {
            return (int)i;
        }
    }
    return -1;
}

bool neko_protocol_request_id_is_valid(const char *request_id)
{
    size_t i;
    size_t len;
    if (request_id == NULL) {
        return false;
    }
    len = strlen(request_id);
    if (len == 0 || len > NEKO_REQUEST_ID_MAX) {
        return false;
    }
    for (i = 0; i < len; i++) {
        unsigned char ch = (unsigned char)request_id[i];
        if (!isalnum(ch) && ch != '_' && ch != '-') {
            return false;
        }
    }
    return true;
}

static bool provider_is_valid(const char *provider, bool is_demo)
{
    if (provider == NULL || provider[0] == '\0') {
        return false;
    }
    if (!is_demo && strstr(provider, "mock") != NULL) {
        return false;
    }
    return true;
}

static bool state_from_string(const char *text, neko_mac_state_t *state)
{
    if (strcmp(text, "idle") == 0) {
        *state = NEKO_MAC_STATE_IDLE;
    } else if (strcmp(text, "checking") == 0) {
        *state = NEKO_MAC_STATE_CHECKING;
    } else if (strcmp(text, "ready") == 0) {
        *state = NEKO_MAC_STATE_READY;
    } else if (strcmp(text, "recording") == 0) {
        *state = NEKO_MAC_STATE_RECORDING;
    } else if (strcmp(text, "paused") == 0) {
        *state = NEKO_MAC_STATE_PAUSED;
    } else if (strcmp(text, "processing") == 0) {
        *state = NEKO_MAC_STATE_PROCESSING;
    } else if (strcmp(text, "completed") == 0) {
        *state = NEKO_MAC_STATE_COMPLETED;
    } else if (strcmp(text, "error") == 0) {
        *state = NEKO_MAC_STATE_ERROR;
    } else if (strcmp(text, "recovery") == 0) {
        *state = NEKO_MAC_STATE_RECOVERY;
    } else {
        return false;
    }
    return true;
}

neko_protocol_status_t neko_protocol_parse_mac_line(const char *line,
                                                    neko_mac_message_t *out)
{
    static const char *required_keys[] = {
        "v", "type", "request_id", "session_id", "state"
    };
    key_seen_t keys[] = {
        {"v", false},
        {"type", false},
        {"request_id", false},
        {"session_id", false},
        {"state", false},
        {"is_demo", false},
        {"asr_provider", false},
        {"topic_provider", false},
        {"topics", false},
        {"summary", false},
        {"code", false},
        {"message", false},
        {"voice", false},
        {"journey", false},
        {"duration_seconds", false},
        {"subject", false},
        {"trend_text", false},
        {"trend", false},
        {"diagnostic", false},
    };
    const char *p = line;
    char type[16] = {0};
    int version = 0;
    size_t i;

    if (line == NULL || out == NULL) {
        return NEKO_PROTOCOL_ERR_NULL;
    }
    if (strlen(line) >= NEKO_PROTOCOL_MAX_LINE_BYTES) {
        return NEKO_PROTOCOL_ERR_TOO_LONG;
    }
    memset(out, 0, sizeof(*out));

    skip_ws(&p);
    if (*p != '{') {
        return NEKO_PROTOCOL_ERR_JSON;
    }
    p++;
    skip_ws(&p);
    while (*p != '\0' && *p != '}') {
        char key[32] = {0};
        char scratch[NEKO_RESULT_SUMMARY_MAX + 1] = {0};
        bool truncated = false;
        bool invalid_field = false;
        int idx;

        if (!parse_json_string(&p, key, sizeof(key), &truncated) || truncated) {
            return NEKO_PROTOCOL_ERR_JSON;
        }
        idx = key_index(key, keys, sizeof(keys) / sizeof(keys[0]));
        if (idx < 0) {
            return NEKO_PROTOCOL_ERR_INVALID_FIELD;
        }
        if (keys[idx].seen) {
            return NEKO_PROTOCOL_ERR_DUPLICATE_KEY;
        }
        keys[idx].seen = true;

        skip_ws(&p);
        if (*p != ':') {
            return NEKO_PROTOCOL_ERR_JSON;
        }
        p++;
        skip_ws(&p);

        if (strcmp(key, "v") == 0) {
            if (!parse_int_value(&p, &version) || version != 1) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "type") == 0) {
            if (!parse_json_string(&p, type, sizeof(type), &truncated) || truncated) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
            if (strcmp(type, "state") == 0) {
                out->kind = NEKO_MAC_STATE;
            } else if (strcmp(type, "result") == 0) {
                out->kind = NEKO_MAC_RESULT;
            } else if (strcmp(type, "error") == 0) {
                out->kind = NEKO_MAC_ERROR;
            } else {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "request_id") == 0) {
            if (!parse_json_string(&p, out->request_id, sizeof(out->request_id),
                                   &truncated)
                || truncated
                || !neko_protocol_request_id_is_valid(out->request_id)) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "session_id") == 0) {
            if (parse_literal(&p, "null")) {
                out->session_id = 0;
                out->has_session_id = false;
            } else if (parse_int_value(&p, &out->session_id)) {
                out->has_session_id = true;
            } else {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "state") == 0) {
            if (!parse_json_string(&p, scratch, sizeof(scratch), &truncated)
                || truncated
                || !state_from_string(scratch, &out->state)) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "is_demo") == 0) {
            if (!parse_bool_value(&p, &out->is_demo)) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "asr_provider") == 0) {
            if (!parse_json_string(&p, out->asr_provider,
                                   sizeof(out->asr_provider), &truncated)
                || truncated) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "topic_provider") == 0) {
            if (!parse_json_string(&p, out->topic_provider,
                                   sizeof(out->topic_provider), &truncated)
                || truncated) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "topics") == 0) {
            if (!parse_topics(&p, out, &invalid_field)) {
                return invalid_field ? NEKO_PROTOCOL_ERR_INVALID_FIELD
                                     : NEKO_PROTOCOL_ERR_JSON;
            }
        } else if (strcmp(key, "summary") == 0) {
            if (!parse_json_string(&p, out->summary, sizeof(out->summary),
                                   &truncated)
                || truncated) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "code") == 0) {
            if (!parse_json_string(&p, out->code, sizeof(out->code), &truncated)
                || truncated) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "message") == 0) {
            if (!parse_json_string(&p, out->message, sizeof(out->message),
                                   &truncated)
                || truncated) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "voice") == 0) {
            if (!parse_voice(&p, out)) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "journey") == 0) {
            if (!parse_journey(&p, out)) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "duration_seconds") == 0) {
            if (!parse_nonnegative_int_value(&p, &out->duration_seconds)) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "subject") == 0) {
            if (!parse_json_string(&p, out->subject, sizeof(out->subject),
                                   &truncated)
                || truncated) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "trend_text") == 0) {
            if (!parse_json_string(&p, out->trend_text, sizeof(out->trend_text),
                                   &truncated)
                || truncated) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "trend") == 0) {
            if (!skip_json_value(&p)) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        } else if (strcmp(key, "diagnostic") == 0) {
            if (!parse_diagnostic(&p, out)) {
                return NEKO_PROTOCOL_ERR_INVALID_FIELD;
            }
        }

        skip_ws(&p);
        if (*p == ',') {
            p++;
            skip_ws(&p);
            continue;
        }
        if (*p != '}') {
            return NEKO_PROTOCOL_ERR_JSON;
        }
    }
    if (*p != '}') {
        return NEKO_PROTOCOL_ERR_JSON;
    }
    p++;
    skip_ws(&p);
    if (*p != '\0') {
        return NEKO_PROTOCOL_ERR_JSON;
    }

    for (i = 0; i < sizeof(required_keys) / sizeof(required_keys[0]); i++) {
        int idx = key_index(required_keys[i], keys, sizeof(keys) / sizeof(keys[0]));
        if (idx < 0 || !keys[idx].seen) {
            return NEKO_PROTOCOL_ERR_MISSING_FIELD;
        }
    }
    if (out->kind == NEKO_MAC_RESULT) {
        if (out->state != NEKO_MAC_STATE_COMPLETED
            || !out->has_session_id
            || !keys[key_index("is_demo", keys, sizeof(keys) / sizeof(keys[0]))].seen
            || !keys[key_index("asr_provider", keys, sizeof(keys) / sizeof(keys[0]))].seen
            || !keys[key_index("topic_provider", keys, sizeof(keys) / sizeof(keys[0]))].seen
            || !keys[key_index("topics", keys, sizeof(keys) / sizeof(keys[0]))].seen
            || !keys[key_index("summary", keys, sizeof(keys) / sizeof(keys[0]))].seen
            || out->summary[0] == '\0'
            || !provider_is_valid(out->asr_provider, out->is_demo)
            || !provider_is_valid(out->topic_provider, out->is_demo)) {
            return NEKO_PROTOCOL_ERR_INVALID_FIELD;
        }
    }
    if (out->kind == NEKO_MAC_ERROR) {
        if (out->state != NEKO_MAC_STATE_ERROR
            || !keys[key_index("code", keys, sizeof(keys) / sizeof(keys[0]))].seen
            || !keys[key_index("message", keys, sizeof(keys) / sizeof(keys[0]))].seen
            || out->code[0] == '\0'
            || out->message[0] == '\0') {
            return NEKO_PROTOCOL_ERR_INVALID_FIELD;
        }
    }
    return NEKO_PROTOCOL_OK;
}

const char *neko_protocol_status_name(neko_protocol_status_t status)
{
    switch (status) {
    case NEKO_PROTOCOL_OK:
        return "ok";
    case NEKO_PROTOCOL_ERR_NULL:
        return "null";
    case NEKO_PROTOCOL_ERR_TOO_LONG:
        return "too_long";
    case NEKO_PROTOCOL_ERR_JSON:
        return "json";
    case NEKO_PROTOCOL_ERR_DUPLICATE_KEY:
        return "duplicate_key";
    case NEKO_PROTOCOL_ERR_MISSING_FIELD:
        return "missing_field";
    case NEKO_PROTOCOL_ERR_INVALID_FIELD:
        return "invalid_field";
    default:
        return "unknown";
    }
}
