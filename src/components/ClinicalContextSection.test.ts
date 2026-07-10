import { describe, expect, it } from "vitest";

import {
  clinicalEmptyActionLabel,
  clinicalRecordLabel,
  clinicalSectionStatusLabel,
  createClinicalPayload,
} from "./ClinicalContextSection";

const state = (
  review_state: "unknown" | "deferred" | "confirmed_none",
  effective_state: "unknown" | "deferred" | "confirmed_none" | "has_entries",
  active_count = 0,
  history_count = 0,
) => ({
  review_state,
  effective_state,
  reviewed_at: null,
  updated_at: null,
  active_count,
  history_count,
});

describe("Clinical Context presentation helpers", () => {
  it("builds safe default payloads for every section", () => {
    expect(createClinicalPayload("conditions", "Головная боль")).toEqual({
      display_name: "Головная боль",
      clinical_status: "active",
    });
    expect(createClinicalPayload("allergies", "Орехи")).toEqual({
      substance_name: "Орехи",
      allergy_type: "unknown",
      clinical_status: "active",
    });
    expect(createClinicalPayload("medications", "Препарат")).toEqual({
      display_name: "Препарат",
      status: "active",
    });
    expect(createClinicalPayload("supplements", "Магний")).toEqual({
      display_name: "Магний",
      supplement_type: "unknown",
      status: "active",
    });
  });

  it("distinguishes all effective review states", () => {
    expect(clinicalSectionStatusLabel(state("unknown", "unknown"))).toBe("Пока не заполнено");
    expect(clinicalSectionStatusLabel(state("deferred", "deferred"))).toBe("Можно заполнить позже");
    expect(clinicalSectionStatusLabel(state("confirmed_none", "confirmed_none"))).toBe("Подтверждено отсутствие");
    expect(clinicalSectionStatusLabel(state("unknown", "has_entries", 2, 3))).toBe("Активных записей: 2");
    expect(clinicalSectionStatusLabel(state("unknown", "has_entries", 0, 3))).toBe("Есть история");
  });

  it("uses substance name for allergy records", () => {
    expect(clinicalRecordLabel({ id: "1", substance_name: "Пенициллин" })).toBe("Пенициллин");
  });

  it("makes confirmed-empty actions explicit", () => {
    expect(clinicalEmptyActionLabel("аллергий и непереносимостей нет")).toBe(
      "Подтвердить: аллергий и непереносимостей нет",
    );
  });
});
