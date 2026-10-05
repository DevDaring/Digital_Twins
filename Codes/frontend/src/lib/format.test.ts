import { describe, expect, it } from "vitest";
import i18n from "i18next";
import en from "@/i18n/locales/en-IN.json";
import hi from "@/i18n/locales/hi-IN.json";
import { fmtMetric, freqText, outOfTen, pct, signed } from "./format";

const t = i18n.createInstance();
await t.init({
  lng: "en-IN",
  resources: { "en-IN": { translation: en }, "hi-IN": { translation: hi } },
  interpolation: { escapeValue: false },
});

describe("frequency text", () => {
  it("rounds to times out of 10", () => {
    expect(outOfTen(0.68)).toBe(7);
    expect(outOfTen(0.04)).toBe(0);
    expect(outOfTen(1.4)).toBe(10);
  });
  it("uses natural English", () => {
    const en = t.getFixedT("en-IN");
    expect(freqText(en, 0.7)).toBe("about 7 times out of 10");
    expect(freqText(en, 0.1)).toBe("about 1 time out of 10");
    expect(freqText(en, 0.02)).toBe("less than 1 time out of 10");
    expect(freqText(en, 0.97)).toBe("almost every time");
  });
  it("localises with Western digits", () => {
    const hiT = t.getFixedT("hi-IN");
    const s = freqText(hiT, 0.7);
    expect(s).toContain("7");
    expect(s).toContain("10");
    expect(s).not.toBe("about 7 times out of 10");
  });
});

describe("number formatting", () => {
  it("percent and sign", () => {
    expect(pct(0.456)).toBe(46);
    expect(signed(12.4)).toBe("+12");
    expect(signed(-3.26, 1)).toBe("−3.3");
    expect(signed(0)).toBe("±0");
  });
  it("formats metrics defensively", () => {
    expect(fmtMetric(0.912, "coverage90")).toBe("91%");
    expect(fmtMetric(0.85, "auroc_high")).toBe("0.85");
    expect(fmtMetric(18.64, "rmse_60")).toBe("18.6");
    expect(fmtMetric(undefined)).toBe("—");
    expect(fmtMetric("CGMacros")).toBe("CGMacros");
  });
});

describe("swapLabel", () => {
  it("uses the backend's localised label, else the English one (flagged)", async () => {
    const { swapLabel } = await import("./format");
    expect(swapLabel({ label: "सफ़ेद चावल की जगह ब्राउन राइस खाएँ", label_en: "Swap white rice for brown rice" }, "hi-IN")).toEqual({ text: "सफ़ेद चावल की जगह ब्राउन राइस खाएँ", english: false });
    expect(swapLabel({ label: "Swap white rice for brown rice", label_en: "Swap white rice for brown rice" }, "hi-IN")).toEqual({ text: "Swap white rice for brown rice", english: true });
    expect(swapLabel({ label_en: "Swap white rice for brown rice" }, "en-IN")).toEqual({ text: "Swap white rice for brown rice", english: false });
  });
});
