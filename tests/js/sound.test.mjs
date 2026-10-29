import { test } from "node:test";
import assert from "node:assert/strict";
import { pickVariant } from "../../static/js/sound.js";

test("single variant always 0", () => {
  assert.equal(pickVariant(1, 0), 0);
  assert.equal(pickVariant(1, -1), 0);
});

test("never repeats the last variant", () => {
  for (let last = 0; last < 3; last++)
    for (const r of [0, 0.34, 0.5, 0.99]) {
      const i = pickVariant(3, last, () => r);
      assert.ok(i >= 0 && i < 3 && i !== last);
    }
});
