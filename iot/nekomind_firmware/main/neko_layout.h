#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "neko_controller.h"

#ifdef __cplusplus
extern "C" {
#endif

#define NEKO_LAYOUT_HIT_TARGET_MIN 44
#define NEKO_LAYOUT_MAX_HITS 8
#define NEKO_SCENE_MAX_OPS 48
#define NEKO_SCENE_TEXT_MAX 48

typedef struct {
    int x;
    int y;
    int width;
    int height;
} neko_layout_rect_t;

typedef struct {
    neko_touch_event_t event;
    neko_layout_rect_t rect;
    bool enabled;
    char label[NEKO_SCENE_TEXT_MAX];
} neko_layout_hit_t;

typedef struct {
    int width;
    int height;
    bool landscape;
    bool reduced_motion;
    bool dark_theme;
    neko_layout_rect_t face;
    neko_layout_rect_t primary_action;
    neko_layout_rect_t secondary_action;
    neko_layout_rect_t previous_action;
    neko_layout_rect_t next_action;
    neko_layout_hit_t hits[NEKO_LAYOUT_MAX_HITS];
    size_t hit_count;
    size_t card_count;
    size_t card_index;
} neko_layout_model_t;

typedef enum {
    NEKO_SCENE_OP_FACE = 1,
    NEKO_SCENE_OP_ELLIPSE,
    NEKO_SCENE_OP_POLYGON,
    NEKO_SCENE_OP_LINE,
    NEKO_SCENE_OP_TEXT,
    NEKO_SCENE_OP_BUTTON
} neko_scene_op_kind_t;

typedef struct {
    neko_scene_op_kind_t kind;
    neko_layout_rect_t rect;
    char text[NEKO_SCENE_TEXT_MAX];
    bool enabled;
} neko_scene_op_t;

typedef struct {
    int width;
    int height;
    bool reduced_motion;
    bool dark_theme;
    size_t op_count;
    neko_scene_op_t ops[NEKO_SCENE_MAX_OPS];
} neko_scene_t;

typedef struct {
    bool was_pressed;
    uint32_t last_edge_ms;
} neko_touch_edge_t;

bool neko_layout_build(neko_controller_state_t state,
                       const neko_controller_view_t *view,
                       int width,
                       int height,
                       bool reduced_motion,
                       size_t requested_card_index,
                       neko_layout_model_t *out);
void neko_layout_set_theme(neko_layout_model_t *layout, bool dark_theme);
bool neko_layout_hit_test(const neko_layout_model_t *layout,
                          int x,
                          int y,
                          neko_touch_event_t *out_event,
                          bool *out_enabled);
bool neko_scene_build(neko_controller_state_t state,
                      const neko_controller_view_t *view,
                      const neko_layout_model_t *layout,
                      neko_scene_t *out);
void neko_touch_edge_init(neko_touch_edge_t *edge);
bool neko_touch_edge_update(neko_touch_edge_t *edge,
                            bool pressed,
                            uint32_t now_ms);

#ifdef __cplusplus
}
#endif
