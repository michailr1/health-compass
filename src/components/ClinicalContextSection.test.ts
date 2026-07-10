import { describe, expect, it } from "vitest";

import {
  clinicalEmptyActionLabel,
  clinicalRecordLabel,
  clinicalSectionStatusLabel,
  createClinicalPayload,
} from "./ClinicalContextSection";

describe("Clinical Context presentation helpers", () => {
  it("builds safe default payloads for every section", () => {
    expect(createClinicalPayload("conditions", "Гипертония")).toEqual({
      display_name: "Гипертония",
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

  it("distinguishes not-filled, reviewed, confirmed-empty and active states", () => {
    expect(clinicalSectionStatusLabel({
      reviewed: false,
      confirmed_empty: false,
      reviewed_at: null,
      active_count: 0,
      total_count: 0,
    })).toBe("Пока не заполнено");

    expect(clinicalSectionStatusLabel({
      reviewed: true,
      confirmed_empty: false,
      reviewed_at: "2026-07-09T12:00:00Z",
      active_count: 0,
      total_count: 0,
    })).toBe("Раздел просмотрен");

    expect(clinicalSectionStatusLabel({
      reviewed: true,
      confirmed_empty: true,
      reviewed_at: "2026-07-09T12:00:00Z",
      active_count: 0,
      total_count: 0,
    })).toBe("Подтверждено отсутствие");

    expect(clinicalSectionStatusLabel({
      reviewed: true,
      confirmed_empty: false,
      reviewed_at: "2026-07-09T12:00:00Z",
      active_count: 2,
      total_count: 3,
    })).toBe("Активных записей: 2");
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
