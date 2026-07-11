import { afterEach, describe, expect, it } from "vitest";

import { formatDateOnlyRu, localDateOnlyISO } from "./utils";

const originalTz = process.env.TZ;

afterEach(() => {
  process.env.TZ = originalTz;
});

describe("date-only handling (HC-015 Slice F / CR-17)", () => {
  it.each(["America/New_York", "Asia/Tokyo"])(
    "formats YYYY-MM-DD without a calendar shift in %s",
    (timezone) => {
      process.env.TZ = timezone;
      expect(formatDateOnlyRu("2026-07-11")).toBe("11.07.2026");
      expect(formatDateOnlyRu("2026-01-01")).toBe("01.01.2026");
    },
  );

  it("passes through values that are not date-only strings", () => {
    expect(formatDateOnlyRu("не дата")).toBe("не дата");
  });

  it("produces the local calendar date for course completion", () => {
    // 23:30 local on July 11 must never serialize as July 12 or July 10.
    const lateEvening = new Date(2026, 6, 11, 23, 30, 0);
    expect(localDateOnlyISO(lateEvening)).toBe("2026-07-11");
    const earlyMorning = new Date(2026, 6, 11, 0, 15, 0);
    expect(localDateOnlyISO(earlyMorning)).toBe("2026-07-11");
  });
});
