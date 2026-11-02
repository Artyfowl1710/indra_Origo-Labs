import { describe, expect, it } from "vitest";
import { defaultTheme, midnightTheme,emberTheme,nousBlueTheme,defaultLargeTheme } from "./presets";

function luminance(hex: string): number {
  const rgb = hex.slice(1).match(/../g)!.map((part) => {
    const value = parseInt(part, 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
}

function contrast(first: string, second: string): number {
  const a = luminance(first), b = luminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

describe.each([defaultTheme, midnightTheme,emberTheme,nousBlueTheme,defaultLargeTheme])("$label palette", (theme) => {
  it("keeps primary and secondary text readable on the canvas and cards", () => {
    const colors = theme.colorOverrides!;
    for (const surface of [theme.palette.background.hex, colors.card!]) {
      for (const text of [colors.cardForeground!, colors.mutedForeground!]) {
        expect(contrast(text, surface)).toBeGreaterThanOrEqual(4.5);
      }
    }
    expect(contrast(colors.primary!, colors.primaryForeground!)).toBeGreaterThanOrEqual(4.5);
  });

  it("uses system typography without a remote font stylesheet", () => {
    expect(theme.typography.fontUrl).toBeUndefined();
    expect(theme.typography.fontSans).toContain("system-ui");
  });
});
