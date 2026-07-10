import { describe, expect, it } from "vitest";

import { describeSessionAgent } from "./ActiveSessionsCard";

describe("describeSessionAgent", () => {
  it("recognizes mobile Safari", () => {
    expect(
      describeSessionAgent(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1",
      ),
    ).toBe("Мобильное устройство · Safari");
  });

  it("recognizes desktop Chrome", () => {
    expect(
      describeSessionAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
      ),
    ).toBe("Компьютер · Google Chrome");
  });

  it("uses a neutral label when metadata is absent", () => {
    expect(describeSessionAgent(null)).toBe("Неизвестное устройство");
  });
});
