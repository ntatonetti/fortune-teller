// Run with: node --test tests/js/*.test.mjs
import assert from "node:assert/strict";
import test from "node:test";
import { applyMatrix, cornerPinMatrix } from "../../static/js/homography.js";

const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-6, `${a} != ${b}`);

test("corners land exactly where pinned", () => {
  const corners = [[120, 80], [530, 60], [560, 470], [100, 430]];
  const m = cornerPinMatrix(400, 500, corners);
  const src = [[0, 0], [400, 0], [400, 500], [0, 500]];
  src.forEach(([x, y], i) => {
    const [u, v] = applyMatrix(m, x, y);
    close(u, corners[i][0]);
    close(v, corners[i][1]);
  });
});

test("an un-warped rectangle is a pure translate+scale", () => {
  const m = cornerPinMatrix(100, 100, [[10, 20], [210, 20], [210, 220], [10, 220]]);
  close(m[0], 2);
  close(m[5], 2);
  close(m[12], 10);
  close(m[13], 20);
  close(m[3], 0);
  close(m[7], 0);
});

test("degenerate quad returns null", () => {
  assert.equal(cornerPinMatrix(100, 100, [[0, 0], [0, 0], [0, 0], [0, 0]]), null);
});
