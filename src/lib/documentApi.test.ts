import { describe, expect, it } from "vitest";

import {
  DOCUMENT_ACCEPT,
  documentStatusLabel,
  formatDocumentSize,
  scannerStatusLabel,
  type DocumentStatus,
  type ScannerStatus,
} from "./documentApi";

describe("document intake helpers", () => {
  it("formats bounded upload sizes for the Russian UI", () => {
    expect(formatDocumentSize(0)).toBe("0 Б");
    expect(formatDocumentSize(1536)).toBe("1.5 КБ");
    expect(formatDocumentSize(20 * 1024 * 1024)).toBe("20.0 МБ");
    expect(formatDocumentSize(-1)).toBe("—");
  });

  it("has a user-facing label for every document state", () => {
    const statuses: DocumentStatus[] = [
      "uploading",
      "quarantined",
      "scanning",
      "accepted",
      "ocr_queued",
      "processing",
      "review_required",
      "confirmed",
      "rejected",
      "failed",
      "voided",
      "deletion_pending",
      "erased",
    ];
    for (const status of statuses) {
      expect(documentStatusLabel(status)).not.toBe("");
    }
    expect(documentStatusLabel("quarantined")).toBe("В карантине");
  });

  it("has a safe user-facing label for every scanner state", () => {
    const statuses: ScannerStatus[] = [
      "not_scanned",
      "scanning",
      "clean",
      "infected",
      "error",
      "stale",
    ];
    for (const status of statuses) {
      expect(scannerStatusLabel(status)).not.toBe("");
    }
    expect(scannerStatusLabel("infected")).toBe("Отклонён как небезопасный");
    expect(scannerStatusLabel("error")).not.toContain("ClamAV");
  });

  it("advertises only the supported file formats", () => {
    expect(DOCUMENT_ACCEPT).toContain("application/pdf");
    expect(DOCUMENT_ACCEPT).toContain("image/jpeg");
    expect(DOCUMENT_ACCEPT).toContain("image/png");
    expect(DOCUMENT_ACCEPT).not.toContain("svg");
    expect(DOCUMENT_ACCEPT).not.toContain("zip");
  });
});
