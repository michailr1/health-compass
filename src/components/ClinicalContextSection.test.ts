import { describe, expect, it } from "vitest";

import {
  buildRecordPatchPayload,
  clinicalEmptyActionLabel,
  clinicalErrorMessage,
  clinicalRecordLabel,
  clinicalSectionStatusLabel,
  createClinicalPayload,
  isClinicalRecordActive,
  recordEditorInitialState,
} from "./ClinicalContextSection";
import { ApiError } from "@/lib/api";

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
  it("builds safe free-text payloads for every section", () => {
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

  it("maps observable condition answers without diagnosing", () => {
    expect(createClinicalPayload("conditions", "Головная боль", {
      onsetTiming: "long_ago",
      presencePattern: "recurring",
    })).toEqual({
      display_name: "Головная боль",
      clinical_status: "active",
      onset_timing: "long_ago",
      presence_pattern: "recurring",
    });
  });

  it("maps optional medication details only when supplied", () => {
    expect(createClinicalPayload("medications", "Метформин", {
      currentUse: "yes",
      startDate: "2026-01-15",
      doseValue: "500",
      doseUnit: "мг",
      frequencyText: "два раза в день",
      reasonText: "по назначению врача",
    })).toEqual({
      display_name: "Метформин",
      status: "active",
      start_date: "2026-01-15",
      dose_value: 500,
      dose_unit: "мг",
      frequency_text: "два раза в день",
      reason_text: "по назначению врача",
    });
  });

  it("preserves canonical dictionary provenance", () => {
    expect(createClinicalPayload("medications", {
      displayText: "Метформин",
      canonicalConceptId: "11111111-1111-4111-8111-111111111301",
      source: "global",
    })).toEqual({
      display_name: "Метформин",
      status: "active",
      code_system: "health_compass",
      code: "11111111-1111-4111-8111-111111111301",
    });
  });

  it("splits active records from history by section semantics", () => {
    expect(isClinicalRecordActive("conditions", { id: "1", clinical_status: "active", updated_at: "2026-01-01T00:00:00Z" })).toBe(true);
    expect(isClinicalRecordActive("allergies", { id: "2", clinical_status: "resolved", updated_at: "2026-01-01T00:00:00Z" })).toBe(false);
    expect(isClinicalRecordActive("medications", { id: "3", status: "completed", updated_at: "2026-01-01T00:00:00Z" })).toBe(false);
    expect(isClinicalRecordActive("supplements", { id: "4", status: "active", updated_at: "2026-01-01T00:00:00Z" })).toBe(true);
  });

  it("distinguishes all effective review states", () => {
    expect(clinicalSectionStatusLabel(state("unknown", "unknown"))).toBe("Пока не заполнено");
    expect(clinicalSectionStatusLabel(state("deferred", "deferred"))).toBe("Можно заполнить позже");
    expect(clinicalSectionStatusLabel(state("confirmed_none", "confirmed_none"))).toBe("Подтверждено отсутствие");
    expect(clinicalSectionStatusLabel(state("unknown", "has_entries", 2, 3))).toBe("Активных записей: 2");
    expect(clinicalSectionStatusLabel(state("unknown", "has_entries", 0, 3))).toBe("Есть история");
  });

  it("uses substance name for allergy records", () => {
    expect(clinicalRecordLabel({ id: "1", substance_name: "Пенициллин", updated_at: "2026-01-01T00:00:00Z" })).toBe("Пенициллин");
  });

  it("makes confirmed-empty actions explicit", () => {
    expect(clinicalEmptyActionLabel("аллергий и непереносимостей нет")).toBe(
      "Подтвердить: аллергий и непереносимостей нет",
    );
  });
});

describe("record editor payloads (HC-015 Slice F)", () => {
  it("clears an existing dose when both dose fields are emptied", () => {
    const result = buildRecordPatchPayload("medications", {
      name: "Метформин",
      frequency: "",
      doseValue: "",
      doseUnit: "",
    });
    expect(result).toEqual({
      payload: {
        display_name: "Метформин",
        frequency_text: null,
        dose_value: null,
        dose_unit: null,
      },
    });
  });

  it("keeps a fully specified dose", () => {
    const result = buildRecordPatchPayload("supplements", {
      name: "Магний",
      frequency: "утром",
      doseValue: "400",
      doseUnit: "мг",
    });
    expect(result).toEqual({
      payload: {
        display_name: "Магний",
        frequency_text: "утром",
        dose_value: 400,
        dose_unit: "мг",
      },
    });
  });

  it("rejects a half-filled dose pair instead of silently dropping it", () => {
    const result = buildRecordPatchPayload("medications", {
      name: "Метформин",
      frequency: "",
      doseValue: "500",
      doseUnit: "",
    });
    expect(result).toHaveProperty("validationError");
  });

  it("rejects a non-numeric dose", () => {
    const result = buildRecordPatchPayload("medications", {
      name: "Метформин",
      frequency: "",
      doseValue: "пятьсот",
      doseUnit: "мг",
    });
    expect(result).toHaveProperty("validationError");
  });

  it("does not send dose fields for conditions and allergies", () => {
    expect(buildRecordPatchPayload("allergies", {
      name: "Пенициллин",
      frequency: "",
      doseValue: "",
      doseUnit: "",
    })).toEqual({ payload: { substance_name: "Пенициллин" } });
  });
});

describe("record editor state derivation (HC-015 Slice F)", () => {
  it("derives the form from the current record so switching records resets state", () => {
    const first = {
      id: "a",
      display_name: "Метформин",
      dose_value: "500",
      dose_unit: "мг",
      frequency_text: "2 раза в день",
      updated_at: "2026-07-11T00:00:00Z",
    };
    const second = {
      id: "b",
      display_name: "Амлодипин",
      dose_value: null,
      dose_unit: null,
      frequency_text: null,
      updated_at: "2026-07-11T00:00:00Z",
    };
    expect(recordEditorInitialState(first)).toEqual({
      name: "Метформин",
      frequency: "2 раза в день",
      doseValue: "500",
      doseUnit: "мг",
    });
    expect(recordEditorInitialState(second)).toEqual({
      name: "Амлодипин",
      frequency: "",
      doseValue: "",
      doseUnit: "",
    });
  });
});

describe("clinical error presentation (HC-015 Slice F)", () => {
  it("keeps the backend request id visible for support", () => {
    const message = clinicalErrorMessage(new ApiError(500, "An internal error occurred", "internal_error", "rid-42"));
    expect(message).toContain("rid-42");
  });

  it("maps 409 conflicts to a safe friendly message", () => {
    const message = clinicalErrorMessage(new ApiError(409, "review_state_conflict", null, "rid-9"));
    expect(message).toContain("Обновите страницу");
    expect(message).toContain("rid-9");
    expect(message).not.toContain("review_state_conflict");
  });
});
