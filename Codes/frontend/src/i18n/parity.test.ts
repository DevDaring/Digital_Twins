import { describe, expect, it } from "vitest";
import en from "./locales/en-IN.json";
import hi from "./locales/hi-IN.json";
import bn from "./locales/bn-IN.json";
import kn from "./locales/kn-IN.json";

type Tree = { [k: string]: string | Tree };

function flatten(obj: Tree, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "string") out[key] = v;
    else Object.assign(out, flatten(v, key));
  }
  return out;
}

const placeholders = (s: string) => (s.match(/\{\{\s*\w+\s*\}\}/g) ?? []).map((p) => p.replace(/\s/g, "")).sort();

const base = flatten(en as Tree);
const locales = { "hi-IN": hi, "bn-IN": bn, "kn-IN": kn } as Record<string, Tree>;

describe("i18n key parity", () => {
  for (const [name, data] of Object.entries(locales)) {
    const flat = flatten(data);
    it(`${name} has exactly the English keys`, () => {
      expect(Object.keys(flat).sort()).toEqual(Object.keys(base).sort());
    });
    it(`${name} keeps every placeholder`, () => {
      for (const [k, v] of Object.entries(base)) {
        expect(placeholders(flat[k] ?? ""), `${name}:${k}`).toEqual(placeholders(v));
      }
    });
    it(`${name} has no empty strings`, () => {
      for (const [k, v] of Object.entries(flat)) expect(v.trim().length, `${name}:${k}`).toBeGreaterThan(0);
    });
    it(`${name} keeps the emergency number in the disclaimer`, () => {
      expect(flat["footer.disclaimer"]).toContain("108");
    });
  }
});
