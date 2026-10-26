import assert from "node:assert/strict";
import test from "node:test";

import { shouldDeferPresenterRefresh } from "../web/src/presenter_refresh.mjs";
import { renderPresenter } from "../web/src/render.mjs";

test("status refresh leaves focused login and editing fields in place", () => {
  const root = { contains: (field) => field.inside };
  for (const kind of ["input", "textarea", "select"]) {
    assert.equal(shouldDeferPresenterRefresh(root, { inside: true, matches: (selector) => selector.includes(kind) }), true);
  }
  assert.equal(shouldDeferPresenterRefresh(root, { inside: false, matches: () => true }), false);
  assert.equal(shouldDeferPresenterRefresh(root, { inside: true, matches: () => false }), false);
  assert.equal(shouldDeferPresenterRefresh(root, null, true), true);
});

test("login error stays beside the token field and escapes markup", () => {
  const html = renderPresenter({ state: "idle" }, { hasToken: false, authError: '<script>alert(1)</script>' });
  assert.match(html, /id="presenter-token-error"/);
  assert.match(html, /aria-describedby="presenter-token-error"/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});
