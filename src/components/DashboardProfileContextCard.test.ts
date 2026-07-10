import { describe, expect, it } from "vitest";

import { profileContextMessage } from "./DashboardProfileContextCard";

const completion = (progress_percent: number, completed_sections: number) => ({
  completed_sections,
  total_sections: 5,
  progress_percent,
  next_section: progress_percent === 100 ? null : "conditions",
  sections: [],
});

describe("profileContextMessage", () => {
  it("does not block an empty profile", () => {
    expect(profileContextMessage(completion(0, 0))).toContain("Дашборд продолжит работать");
  });

  it("describes partial context without coercion", () => {
    expect(profileContextMessage(completion(40, 2))).toContain("не обязательно для работы сервиса");
  });

  it("describes completed review without medical certainty claims", () => {
    expect(profileContextMessage(completion(100, 5))).toContain("Основные разделы профиля просмотрены");
  });
});
