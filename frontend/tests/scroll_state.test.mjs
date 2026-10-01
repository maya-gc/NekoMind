import assert from "node:assert/strict";
import test from "node:test";

import { captureTextareaScroll, restoreTextareaScroll } from "../web/src/scroll_state.mjs";

const root = (fields) => ({ querySelectorAll: () => fields });

test("periodic redraw keeps each textarea at its own scroll position", () => {
  const before = root([
    { value: "long article", scrollTop: 420, scrollLeft: 0 },
    { value: "point one\npoint two", scrollTop: 85, scrollLeft: 3 },
  ]);
  const positions = captureTextareaScroll(before);
  const afterFields = [
    { value: "long article", scrollTop: 0, scrollLeft: 0 },
    { value: "point one\npoint two", scrollTop: 0, scrollLeft: 0 },
  ];
  restoreTextareaScroll(root(afterFields), positions);
  assert.deepEqual(afterFields.map((field) => [field.scrollTop, field.scrollLeft]), [[420, 0], [85, 3]]);
});

test("newly imported text starts at the top", () => {
  const positions = captureTextareaScroll(root([{ value: "old article", scrollTop: 300 }]));
  const field = { value: "new article", scrollTop: 0, scrollLeft: 0 };
  restoreTextareaScroll(root([field]), positions);
  assert.equal(field.scrollTop, 0);
});
