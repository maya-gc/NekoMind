import assert from "node:assert/strict";
import test from "node:test";

import { assessmentBadge, renderReview } from "../web/src/render.mjs";

test("assessment badge explains AI judgement without grading", () => {
  assert.match(assessmentBadge({ assessment: "equivoco" }), /equívoco/);
  assert.match(assessmentBadge({ assessment: "parcial" }), /não é nota/);
  assert.equal(assessmentBadge({ assessment: "" }), "");
  assert.equal(assessmentBadge(null), "");
});

test("review list escapes markup and hides when empty", () => {
  const html = renderReview([{ point: "<b>Hamiltoniana</b>", status: "parcial" }]);
  assert.match(html, /Revisar hoje/);
  assert.match(html, /&lt;b&gt;Hamiltoniana/);
  assert.equal(renderReview([]), "");
});
