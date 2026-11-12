#!/usr/bin/env node
import { slugify } from "../src/slugify.js";

const args = process.argv.slice(2);
const title = args.find((a) => !a.startsWith("--")) ?? "";
console.log(slugify(title));
