#include "neko_layout.h"

#include <stdio.h>
#include <string.h>

static int clamp_int(int value, int min_value, int max_value)
{
    if (value < min_value) {
        return min_value;
    }
    if (value > max_value) {
        return max_value;
    }
    return value;
}

static bool has_text(const char *text)
{
    return text != NULL && text[0] != '\0';
}

static size_t result_card_count(const neko_controller_view_t *view)
{
    size_t count = 0;
    if (view == NULL) {
        return 0;
    }
    if (has_text(view->summary)) {
        count++;
    }
    if (view->topic_count > 0) {
        count += view->topic_count;
    }
    if (view->duration_seconds > 0) {
        count++;
    }
    if (has_text(view->trend_text)) {
        count++;
    }
    return count;
}

static void add_hit(neko_layout_model_t *model,
                    neko_touch_event_t event,
                    neko_layout_rect_t rect,
                    bool enabled,
                    const char *label)
{
    if (model->hit_count >= NEKO_LAYOUT_MAX_HITS) {
        return;
    }
    model->hits[model->hit_count].event = event;
    model->hits[model->hit_count].rect = rect;
    model->hits[model->hit_count].enabled = enabled;
    snprintf(model->hits[model->hit_count].label,
             sizeof(model->hits[model->hit_count].label), "%s",
             label != NULL ? label : "");
    model->hit_count++;
}

static neko_layout_rect_t rect_make(int x, int y, int width, int height)
{
    neko_layout_rect_t rect;
    rect.x = x;
    rect.y = y;
    rect.width = width;
    rect.height = height;
    return rect;
}

static void build_portrait(neko_controller_state_t state, neko_layout_model_t *out)
{
    int face_h = state == NEKO_CONTROLLER_SUCCESS ? 104 : 150;
    int face_w = clamp_int(out->width - 48, 120, 176);
    int action_y = out->height - 58;

    out->face = rect_make((out->width - face_w) / 2, 36, face_w, face_h);
    out->primary_action = rect_make(12, action_y, out->width - 24, 48);
    out->secondary_action = rect_make(12, action_y - 50, out->width - 24, 44);
    out->previous_action = rect_make(12, action_y, 54, 48);
    out->next_action = rect_make(out->width - 66, action_y, 54, 48);
}

static void build_landscape(neko_controller_state_t state, neko_layout_model_t *out)
{
    int face_w = state == NEKO_CONTROLLER_SUCCESS ? 126 : 142;
    int face_h = clamp_int(out->height - 52, 120, 152);
    int action_x = face_w + 24;
    int action_w = out->width - action_x - 12;
    int action_y = out->height - 56;

    out->face = rect_make(12, 28, face_w, face_h);
    out->primary_action = rect_make(action_x, action_y, action_w, 46);
    out->secondary_action = rect_make(action_x, action_y - 48, action_w, 44);
    out->previous_action = rect_make(action_x, action_y, 54, 46);
    out->next_action = rect_make(out->width - 66, action_y, 54, 46);
}

static neko_layout_rect_t action_slot(const neko_layout_model_t *model,
                                      size_t index,
                                      size_t count)
{
    if (model->landscape) {
        int h = 46;
        int gap = 6;
        if (count >= 3) {
            int rows = (int)((count + 1U) / 2U);
            int y = model->height - rows * h - (rows - 1) * gap - 8;
            int w = (model->width - model->face.width - 38 - gap) / 2;
            int x0 = model->face.x + model->face.width + 14;
            int col = (int)(index % 2U);
            int row = (int)(index / 2U);
            return rect_make(x0 + col * (w + gap), y + row * (h + gap), w, h);
        } else {
            int x = model->face.x + model->face.width + 14;
            int available_w = model->width - x - 12;
            int total_h = (int)count * h + (int)(count - 1U) * gap;
            int y = model->height - total_h - 8;
            return rect_make(x, y + (int)index * (h + gap), available_w, h);
        }
    }
    if (count >= 3) {
        int h = 46;
        int gap = 6;
        int rows = (int)((count + 1U) / 2U);
        int w = (model->width - 24 - gap) / 2;
        int col = (int)(index % 2U);
        int row = (int)(index / 2U);
        int y = model->height - rows * h - (rows - 1) * gap - 10;
        return rect_make(12 + col * (w + gap), y + row * (h + gap), w, h);
    }
    {
        int h = 46;
        int gap = 6;
        int total_h = (int)count * h + (int)(count - 1U) * gap;
        int y = model->height - total_h - 10;
        return rect_make(12, y + (int)index * (h + gap), model->width - 24, h);
    }
}

static void add_state_actions(neko_controller_state_t state, neko_layout_model_t *out)
{
    switch (state) {
    case NEKO_CONTROLLER_IDLE:
        add_hit(out, NEKO_TOUCH_DIAGNOSE, action_slot(out, 0, 2), true, "Diagnostico");
        add_hit(out, NEKO_TOUCH_RESET, action_slot(out, 1, 2), true, "Reset");
        break;
    case NEKO_CONTROLLER_CHECKING:
        add_hit(out, NEKO_TOUCH_CANCEL, action_slot(out, 0, 1), true, "Cancelar");
        break;
    case NEKO_CONTROLLER_READY:
        add_hit(out, NEKO_TOUCH_START, action_slot(out, 0, 3), true, "Comecar");
        add_hit(out, NEKO_TOUCH_CALIBRATE, action_slot(out, 1, 3), true, "Calibrar");
        add_hit(out, NEKO_TOUCH_DIAGNOSE, action_slot(out, 2, 3), true, "Diagnostico");
        break;
    case NEKO_CONTROLLER_RECORDING:
        add_hit(out, NEKO_TOUCH_PAUSE, action_slot(out, 0, 3), true, "Pausar");
        add_hit(out, NEKO_TOUCH_FINISH, action_slot(out, 1, 3), true, "Finalizar");
        add_hit(out, NEKO_TOUCH_CANCEL, action_slot(out, 2, 3), true, "Cancelar");
        break;
    case NEKO_CONTROLLER_PAUSED:
        add_hit(out, NEKO_TOUCH_RESUME, action_slot(out, 0, 3), true, "Retomar");
        add_hit(out, NEKO_TOUCH_FINISH, action_slot(out, 1, 3), true, "Finalizar");
        add_hit(out, NEKO_TOUCH_CANCEL, action_slot(out, 2, 3), true, "Cancelar");
        break;
    case NEKO_CONTROLLER_PROCESSING:
        add_hit(out, NEKO_TOUCH_STATUS, action_slot(out, 0, 2), true, "Atualizar");
        add_hit(out, NEKO_TOUCH_CANCEL, action_slot(out, 1, 2), true, "Cancelar");
        break;
    case NEKO_CONTROLLER_SUCCESS:
        add_hit(out, NEKO_TOUCH_PREV_CARD, action_slot(out, 0, 4), out->card_count > 1,
                "Anterior");
        add_hit(out, NEKO_TOUCH_NEXT_CARD, action_slot(out, 1, 4), out->card_count > 1,
                "Proximo");
        add_hit(out, NEKO_TOUCH_RETRY, action_slot(out, 2, 4), true, "Nova tentativa");
        add_hit(out, NEKO_TOUCH_RESET, action_slot(out, 3, 4), true, "Encerrar");
        break;
    case NEKO_CONTROLLER_ERROR:
        add_hit(out, NEKO_TOUCH_RETRY, action_slot(out, 0, 3), true, "Tentar de novo");
        add_hit(out, NEKO_TOUCH_DIAGNOSE, action_slot(out, 1, 3), true, "Diagnostico");
        add_hit(out, NEKO_TOUCH_RESET, action_slot(out, 2, 3), true, "Reset");
        break;
    case NEKO_CONTROLLER_RECOVERY:
        add_hit(out, NEKO_TOUCH_RECOVER, action_slot(out, 0, 3), true, "Retomar");
        add_hit(out, NEKO_TOUCH_DISCARD, action_slot(out, 1, 3), true, "Descartar");
        add_hit(out, NEKO_TOUCH_CANCEL, action_slot(out, 2, 3), true, "Cancelar");
        break;
    case NEKO_CONTROLLER_PENDING:
    default:
        add_hit(out, NEKO_TOUCH_STATUS, action_slot(out, 0, 1), false, "Aguarde");
        break;
    }
}

bool neko_layout_build(neko_controller_state_t state,
                       const neko_controller_view_t *view,
                       int width,
                       int height,
                       bool reduced_motion,
                       size_t requested_card_index,
                       neko_layout_model_t *out)
{
    if (out == NULL || width < 200 || height < 200) {
        return false;
    }
    memset(out, 0, sizeof(*out));
    out->width = width;
    out->height = height;
    out->landscape = width > height;
    out->reduced_motion = reduced_motion;
    out->card_count = state == NEKO_CONTROLLER_SUCCESS
        ? result_card_count(view)
        : 0;
    if (out->card_count == 0 && state == NEKO_CONTROLLER_SUCCESS) {
        out->card_count = 1;
    }
    out->card_index = out->card_count > 0
        ? requested_card_index % out->card_count
        : 0;

    if (out->landscape) {
        build_landscape(state, out);
    } else {
        build_portrait(state, out);
    }

    add_state_actions(state, out);
    return true;
}

bool neko_layout_hit_test(const neko_layout_model_t *layout,
                          int x,
                          int y,
                          neko_touch_event_t *out_event,
                          bool *out_enabled)
{
    size_t i;
    if (layout == NULL || out_event == NULL || out_enabled == NULL) {
        return false;
    }
    for (i = 0; i < layout->hit_count; i++) {
        const neko_layout_rect_t *rect = &layout->hits[i].rect;
        if (x >= rect->x && y >= rect->y
            && x < rect->x + rect->width
            && y < rect->y + rect->height) {
            *out_event = layout->hits[i].event;
            *out_enabled = layout->hits[i].enabled;
            return true;
        }
    }
    return false;
}

static void add_scene_op(neko_scene_t *scene,
                         neko_scene_op_kind_t kind,
                         neko_layout_rect_t rect,
                         const char *text,
                         bool enabled)
{
    if (scene->op_count >= NEKO_SCENE_MAX_OPS) {
        return;
    }
    scene->ops[scene->op_count].kind = kind;
    scene->ops[scene->op_count].rect = rect;
    scene->ops[scene->op_count].enabled = enabled;
    snprintf(scene->ops[scene->op_count].text,
             sizeof(scene->ops[scene->op_count].text), "%s",
             text != NULL ? text : "");
    scene->op_count++;
}

static const char *state_label(neko_controller_state_t state)
{
    switch (state) {
    case NEKO_CONTROLLER_CHECKING:
        return "Verificando";
    case NEKO_CONTROLLER_READY:
        return "Pronto";
    case NEKO_CONTROLLER_RECORDING:
        return "Ouvindo";
    case NEKO_CONTROLLER_PAUSED:
        return "Pausado";
    case NEKO_CONTROLLER_PROCESSING:
        return "Processando";
    case NEKO_CONTROLLER_SUCCESS:
        return "Resultado";
    case NEKO_CONTROLLER_ERROR:
        return "Erro";
    case NEKO_CONTROLLER_RECOVERY:
        return "Recuperacao";
    case NEKO_CONTROLLER_PENDING:
        return "Aguarde";
    case NEKO_CONTROLLER_IDLE:
    default:
        return "Toque para explicar";
    }
}

static const char *face_expression(neko_controller_state_t state,
                                   const neko_controller_view_t *view,
                                   bool reduced_motion)
{
    if (reduced_motion) {
        return "face-static";
    }
    switch (state) {
    case NEKO_CONTROLLER_CHECKING:
        return "face-checking";
    case NEKO_CONTROLLER_RECORDING:
        if (view != NULL && view->voice_clipping) {
            return "face-recording-clipping";
        }
        if (view != NULL && view->voice_quality == NEKO_VOICE_QUALITY_LOW) {
            return "face-recording-low";
        }
        return "face-recording";
    case NEKO_CONTROLLER_PAUSED:
        return "face-paused";
    case NEKO_CONTROLLER_PROCESSING:
        return "face-processing";
    case NEKO_CONTROLLER_SUCCESS:
        return "face-success";
    case NEKO_CONTROLLER_ERROR:
        return "face-error";
    case NEKO_CONTROLLER_RECOVERY:
        return "face-recovery";
    case NEKO_CONTROLLER_READY:
        return "face-ready";
    case NEKO_CONTROLLER_IDLE:
    default:
        return "face-idle";
    }
}

static void add_face_ops(neko_scene_t *scene,
                         const neko_layout_rect_t *face,
                         neko_controller_state_t state,
                         const neko_controller_view_t *view,
                         bool reduced_motion)
{
    int ear_w = face->width / 4;
    int eye_w = face->width / 7;
    int eye_y = face->y + face->height / 3;
    int mouth_y = state == NEKO_CONTROLLER_SUCCESS
        ? face->y + (face->height * 3) / 4
        : face->y + (face->height * 2) / 3;
    add_scene_op(scene, NEKO_SCENE_OP_FACE, *face,
                 face_expression(state, view, reduced_motion), true);
    add_scene_op(scene, NEKO_SCENE_OP_POLYGON,
                 rect_make(face->x + 8, face->y, ear_w, face->height / 3),
                 "orelha esquerda", true);
    add_scene_op(scene, NEKO_SCENE_OP_POLYGON,
                 rect_make(face->x + face->width - ear_w - 8, face->y,
                           ear_w, face->height / 3),
                 "orelha direita", true);
    add_scene_op(scene, NEKO_SCENE_OP_ELLIPSE,
                 rect_make(face->x + face->width / 2 - face->width / 3,
                           face->y + face->height / 7,
                           (face->width * 2) / 3,
                           (face->height * 5) / 7),
                 "cabeca", true);
    add_scene_op(scene, NEKO_SCENE_OP_ELLIPSE,
                 rect_make(face->x + face->width / 3 - eye_w / 2, eye_y,
                           eye_w, eye_w),
                 "olho esquerdo", true);
    add_scene_op(scene, NEKO_SCENE_OP_ELLIPSE,
                 rect_make(face->x + (face->width * 2) / 3 - eye_w / 2, eye_y,
                           eye_w, eye_w),
                 "olho direito", true);
    add_scene_op(scene, NEKO_SCENE_OP_LINE,
                 rect_make(face->x + face->width / 5, mouth_y,
                           (face->width * 3) / 5, 2),
                 state == NEKO_CONTROLLER_RECORDING ? "bigodes-voz" : "bigodes", true);
}

static void utf8_copy_safe(char *out, size_t out_size, const char *text)
{
    size_t n = 0;
    if (out == NULL || out_size == 0) {
        return;
    }
    if (text == NULL) {
        out[0] = '\0';
        return;
    }
    while (text[n] != '\0' && n + 1 < out_size) {
        unsigned char ch = (unsigned char)text[n];
        size_t char_len = 1;
        if ((ch & 0x80U) == 0U) {
            char_len = 1;
        } else if ((ch & 0xE0U) == 0xC0U) {
            char_len = 2;
        } else if ((ch & 0xF0U) == 0xE0U) {
            char_len = 3;
        } else if ((ch & 0xF8U) == 0xF0U) {
            char_len = 4;
        }
        if (n + char_len >= out_size) {
            break;
        }
        n += char_len;
    }
    memcpy(out, text, n);
    out[n] = '\0';
}

static void card_text(const neko_controller_view_t *view,
                      const neko_layout_model_t *layout,
                      char *out,
                      size_t out_size)
{
    size_t index = 0;
    if (view == NULL || layout == NULL || layout->card_count == 0) {
        utf8_copy_safe(out, out_size, "");
        return;
    }
    if (has_text(view->summary)) {
        if (layout->card_index == index) {
            utf8_copy_safe(out, out_size, view->summary);
            return;
        }
        index++;
    }
    if (view->topic_count > 0) {
        size_t topic_index;
        for (topic_index = 0; topic_index < view->topic_count; topic_index++) {
            if (layout->card_index == index) {
                utf8_copy_safe(out, out_size,
                               view->topics != NULL ? view->topics[topic_index] : "");
                return;
            }
            index++;
        }
    }
    if (view->duration_seconds > 0) {
        if (layout->card_index == index) {
            snprintf(out, out_size, "%ds", view->duration_seconds);
            return;
        }
        index++;
    }
    if (has_text(view->trend_text) && layout->card_index == index) {
        utf8_copy_safe(out, out_size, view->trend_text);
        return;
    }
    utf8_copy_safe(out, out_size, "Resultado");
}

bool neko_scene_build(neko_controller_state_t state,
                      const neko_controller_view_t *view,
                      const neko_layout_model_t *layout,
                      neko_scene_t *out)
{
    size_t i;
    neko_layout_rect_t text_rect;
    neko_layout_rect_t badge_rect;
    neko_layout_rect_t card_rect;
    char card[NEKO_SCENE_TEXT_MAX];
    const char *main_text;
    if (layout == NULL || out == NULL) {
        return false;
    }
    memset(out, 0, sizeof(*out));
    out->width = layout->width;
    out->height = layout->height;
    out->reduced_motion = layout->reduced_motion;

    add_face_ops(out, &layout->face, state, view, layout->reduced_motion);
    badge_rect = layout->landscape
        ? rect_make(layout->face.x + layout->face.width + 14, 6, 58, 20)
        : rect_make(12, 6, 58, 20);
    add_scene_op(out, NEKO_SCENE_OP_TEXT, badge_rect,
                 view != NULL && view->is_demo ? "DEMO" : "REAL", true);
    text_rect = layout->landscape
        ? rect_make(layout->face.x + layout->face.width + 14, 30,
                    layout->width - layout->face.x - layout->face.width - 26, 28)
        : rect_make(12, layout->face.y + layout->face.height + 8,
                    layout->width - 24, 16);
    main_text = view != NULL && has_text(view->message)
        ? view->message
        : state_label(state);
    add_scene_op(out, NEKO_SCENE_OP_TEXT, text_rect, main_text, true);
    if (state == NEKO_CONTROLLER_SUCCESS) {
        card_text(view, layout, card, sizeof(card));
        card_rect = layout->landscape
            ? rect_make(text_rect.x, 64, text_rect.width, 42)
            : rect_make(12, text_rect.y + 28, layout->width - 24, 36);
        add_scene_op(out, NEKO_SCENE_OP_TEXT,
                     card_rect, card, true);
    } else if (view != NULL && has_text(view->journey_step)) {
        add_scene_op(out, NEKO_SCENE_OP_TEXT,
                     rect_make(text_rect.x, text_rect.y + 52, text_rect.width, 20),
                     view->journey_step, true);
    } else if (view != NULL && has_text(view->diagnostic_component)) {
        add_scene_op(out, NEKO_SCENE_OP_TEXT,
                     rect_make(text_rect.x, text_rect.y + 52, text_rect.width, 20),
                     view->diagnostic_component, true);
    }
    for (i = 0; i < layout->hit_count; i++) {
        add_scene_op(out, NEKO_SCENE_OP_BUTTON, layout->hits[i].rect,
                     layout->hits[i].label, layout->hits[i].enabled);
    }
    return out->op_count > 0;
}

void neko_touch_edge_init(neko_touch_edge_t *edge)
{
    if (edge == NULL) {
        return;
    }
    edge->was_pressed = false;
    edge->last_edge_ms = 0;
}

bool neko_touch_edge_update(neko_touch_edge_t *edge,
                            bool pressed,
                            uint32_t now_ms)
{
    if (edge == NULL) {
        return false;
    }
    if (!pressed) {
        edge->was_pressed = false;
        return false;
    }
    if (edge->was_pressed) {
        return false;
    }
    edge->was_pressed = true;
    edge->last_edge_ms = now_ms;
    return true;
}
