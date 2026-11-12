// Locked: the builder may not change this file (devloop.json "protect").
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { slugify } from "../src/slugify.js";

const cli = fileURLToPath(new URL("../bin/slugify.js", import.meta.url));
const run = (...args) => execFileSync(process.execPath, [cli, ...args], { encoding: "utf8" }).trim();

test("lowercases and joins words with dashes", () => {
  assert.equal(slugify("Hello World"), "hello-world");
});

test("takes accents off letters", () => {
  assert.equal(slugify("Café Crème Brûlée"), "cafe-creme-brulee");
  assert.equal(slugify("Über Straße"), "uber-strasse");
});

test("& becomes and", () => {
  assert.equal(slugify("Salt & Pepper"), "salt-and-pepper");
  assert.equal(slugify("R&D"), "r-and-d");
});

test("runs of symbols and spaces become one dash, none at the ends", () => {
  assert.equal(slugify("Hello,   world!!"), "hello-world");
  assert.equal(slugify("  --Leading and trailing--  "), "leading-and-trailing");
  assert.equal(slugify("a_b.c/d"), "a-b-c-d");
});

test("keeps digits", () => {
  assert.equal(slugify("Top 10 tips for 2026"), "top-10-tips-for-2026");
});

test("cuts at a dash, never mid-word", () => {
  const s = slugify("The quick brown fox jumps over the lazy dog", { max: 20 });
  assert.equal(s, "the-quick-brown-fox");
  assert.ok(s.length <= 20);
  assert.equal(slugify("one two three", { max: 7 }), "one-two");
  assert.equal(slugify("one two three", { max: 8 }), "one-two");
});

test("a first word longer than max is cut at max", () => {
  assert.equal(slugify("Supercalifragilistic words", { max: 10 }), "supercalif");
});

test("default max is 50", () => {
  const long = Array.from({ length: 30 }, (_, i) => `word${i}`).join(" ");
  const s = slugify(long);
  assert.ok(s.length <= 50, `got ${s.length}`);
  assert.ok(!s.endsWith("-"));
  assert.ok(long.toLowerCase().replace(/ /g, "-").startsWith(s));
});

test("no letters or digits gives an empty string", () => {
  assert.equal(slugify("!!! ???"), "");
  assert.equal(slugify(""), "");
});

test("the command line prints the slug and takes --max", () => {
  assert.equal(run("Café & Crème"), "cafe-and-creme");
  assert.equal(run("--max", "9", "The quick brown fox"), "the-quick");
});
