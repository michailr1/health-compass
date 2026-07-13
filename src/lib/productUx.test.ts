import { describe, expect, it } from "vitest";

import {
  ANALYSES_EMPTY_STATE_COPY,
  PRIMARY_NAVIGATION,
  SECURE_ANALYSES_COPY,
  getEmptyDashboardPrimaryAction,
  isDemoDataSource,
  isPrimaryNavigationActive,
} from "./productUx";

describe("HC-019 product UX contract", () => {
  it("keeps the primary navigation at five task-oriented items", () => {
    expect(PRIMARY_NAVIGATION.map((item) => item.label)).toEqual([
      "Главная",
      "История",
      "Добавить",
      "Ассистент",
      "Ещё",
    ]);
    expect(PRIMARY_NAVIGATION).toHaveLength(5);
    expect(PRIMARY_NAVIGATION.map((item) => item.label)).not.toContain("Документы");
    expect(PRIMARY_NAVIGATION.map((item) => item.label)).not.toContain("Oura");
    expect(PRIMARY_NAVIGATION.map((item) => item.label)).not.toContain("Генетика");
    expect(PRIMARY_NAVIGATION.map((item) => item.label)).not.toContain("План");
    expect(PRIMARY_NAVIGATION.map((item) => item.label)).not.toContain("Источники");
  });

  it("marks exactly the matching primary destination as active", () => {
    const home = PRIMARY_NAVIGATION.find((item) => item.id === "home")!;
    const history = PRIMARY_NAVIGATION.find((item) => item.id === "history")!;
    const more = PRIMARY_NAVIGATION.find((item) => item.id === "more")!;

    expect(isPrimaryNavigationActive(home, "/app")).toBe(true);
    expect(isPrimaryNavigationActive(home, "/app/history")).toBe(false);
    expect(isPrimaryNavigationActive(history, "/app/history")).toBe(true);
    expect(isPrimaryNavigationActive(history, "/app/history/item")).toBe(true);
    expect(isPrimaryNavigationActive(more, "/app/profile")).toBe(true);
    expect(isPrimaryNavigationActive(more, "/app/documents/123/review")).toBe(true);
    expect(isPrimaryNavigationActive(more, "/app/sleep")).toBe(true);
    expect(isPrimaryNavigationActive(more, "/app/oura")).toBe(true);
    expect(isPrimaryNavigationActive(more, "/app/profilex")).toBe(false);
    expect(isPrimaryNavigationActive(more, "/app/add")).toBe(false);
  });

  it("preserves the approved analyses explanation exactly", () => {
    expect(ANALYSES_EMPTY_STATE_COPY).toBe(
      "Загрузите PDF или фото результатов анализов. Мы распознаем значения — вы проверите и подтвердите их, после этого они появятся в показателях, динамике и отчётах. Ничего не станет медицинским фактом без вашего подтверждения.",
    );
  });

  it("uses user-facing secure storage copy without implementation language", () => {
    expect(SECURE_ANALYSES_COPY).toBe(
      "Файл хранится в зашифрованном виде и защищён от постороннего доступа. После проверки файла мы распознаем текст — вы сможете просмотреть и подтвердить результат.",
    );
    expect(SECURE_ANALYSES_COPY.toLowerCase()).not.toContain("карантин");
    expect(SECURE_ANALYSES_COPY.toLowerCase()).not.toContain("путь хранения");
  });

  it("chooses only an executable empty-dashboard action", () => {
    expect(getEmptyDashboardPrimaryAction(false)).toEqual({
      to: "/app/profile",
      label: "Заполнить профиль здоровья",
      description: "Начните с доступного шага: добавьте основные сведения и медицинский контекст.",
    });
    expect(getEmptyDashboardPrimaryAction(true)).toEqual({
      to: "/app/documents",
      label: "Загрузить анализы",
      description: "Добавьте PDF или фото результатов анализов, чтобы начать формировать показатели.",
    });
  });

  it("detects legacy demo and mock dashboard sources without hiding real labels", () => {
    expect(isDemoDataSource("demo-bootstrap")).toBe(true);
    expect(isDemoDataSource("legacy mock snapshot")).toBe(true);
    expect(isDemoDataSource("profile-confirmed-data")).toBe(false);
    expect(isDemoDataSource(null)).toBe(false);
  });
});
