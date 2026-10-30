import { test } from "node:test";
import assert from "node:assert/strict";

// A stand-in for Chrome's speech recognition: tests speak through `hear`.
let rec;
globalThis.window = {
  webkitSpeechRecognition: class {
    constructor() {
      rec = this;
    }
    start() {}
    abort() {}
  },
};
const { Ears } = await import("../../static/js/ears.js");

const hear = (transcript, isFinal = true) =>
  rec.onresult({ resultIndex: 0, results: [Object.assign([{ transcript }], { isFinal })] });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test("a finished question ends after the pause", async () => {
  const ears = new Ears();
  const t0 = performance.now();
  const p = ears.listen({ silenceMs: 200, confirm: async () => true });
  hear("will I get a puppy");
  assert.equal(await p, "will I get a puppy");
  assert.ok(performance.now() - t0 >= 200);
});

test("she keeps listening while the question is unfinished", async () => {
  const ears = new Ears();
  const asked = [];
  const p = ears.listen({ silenceMs: 100, moreMs: 5000, confirm: async (t) => (asked.push(t), t.includes("puppy")) });
  hear("will I");
  await sleep(1200);
  assert.ok(ears.listening, "still listening after a pause mid-sentence");
  hear("get a puppy");
  assert.equal(await p, "will I get a puppy");
  assert.deepEqual(asked, ["will I", "will I get a puppy"]); // each pause is checked once
});

test("an unfinished question gives up after moreMs", async () => {
  const ears = new Ears();
  const t0 = performance.now();
  const p = ears.listen({ silenceMs: 100, moreMs: 400, confirm: async () => false });
  hear("um");
  assert.equal(await p, "um");
  assert.ok(performance.now() - t0 >= 500);
});

test("looking away stops the quiet clock", async () => {
  const ears = new Ears();
  const t0 = performance.now();
  const p = ears.listen({ silenceMs: 100, hold: () => performance.now() - t0 < 700 });
  hear("what should I ask");
  assert.equal(await p, "what should I ask");
  assert.ok(performance.now() - t0 >= 700);
});

test("half-heard words survive Chrome restarting the session", async () => {
  const ears = new Ears();
  const p = ears.listen({ silenceMs: 200 });
  hear("will my cat", false);
  rec.onend();
  hear("learn to talk");
  assert.equal(await p, "will my cat learn to talk");
});

test("the check runs during the pause, not after it", async () => {
  const ears = new Ears();
  const t0 = performance.now();
  const p = ears.listen({ silenceMs: 2000, confirm: () => sleep(1000).then(() => true) });
  hear("will it snow on Halloween");
  await p;
  const took = performance.now() - t0;
  assert.ok(took >= 2000 && took < 2600, `took ${Math.round(took)}ms`);
});
