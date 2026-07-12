import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  Clock3,
  Pencil,
  ShieldCheck,
  UserCheck,
  X,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ApiError, apiGet, type HealthProfile } from "@/lib/api";
import {
  candidateStatusLabel,
  finalizeOCRReview,
  getOCRReview,
  patientDecisionLabel,
  reviewOCRCandidate,
  setOCRPatientDecision,
  type OCRCandidate,
  type OCRPatientDecision,
  type OCRReviewAction,
  type OCRReviewState,
} from "@/lib/documentOcrReviewApi";

function reviewErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      return "Данные изменились или проверка ещё не завершена. Обновите страницу.";
    }
    if (error.status === 428) {
      return "Не хватает версии данных для безопасного сохранения.";
    }
    if (error.status === 422) {
      return "Проверьте заполненные поля.";
    }
    return error.message;
  }
  return "Не удалось сохранить результат проверки.";
}

function confidenceLabel(value: number): string {
  if (value >= 90) return "Высокая уверенность";
  if (value >= 70) return "Средняя уверенность";
  return "Низкая уверенность";
}

interface CandidateCardProps {
  candidate: OCRCandidate;
  disabled: boolean;
  pendingAction: OCRReviewAction | null;
  onAction: (
    candidate: OCRCandidate,
    action: OCRReviewAction,
    reviewedText: string | null,
    reviewNote: string | null,
  ) => void;
}

function CandidateCard({
  candidate,
  disabled,
  pendingAction,
  onAction,
}: CandidateCardProps) {
  const [editedText, setEditedText] = useState(
    candidate.reviewed_text ?? candidate.original_text,
  );
  const [reviewNote, setReviewNote] = useState(candidate.review_note ?? "");

  useEffect(() => {
    setEditedText(candidate.reviewed_text ?? candidate.original_text);
    setReviewNote(candidate.review_note ?? "");
  }, [candidate.original_text, candidate.review_note, candidate.reviewed_text]);

  const isDisabled = disabled || pendingAction !== null;

  return (
    <article className="hm-card p-4 md:p-5" aria-labelledby={`candidate-${candidate.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Страница {candidate.page_number} · фрагмент {candidate.candidate_index + 1}
          </p>
          <h2 id={`candidate-${candidate.id}`} className="mt-1 font-display text-lg font-semibold">
            Распознанный текст
          </h2>
        </div>
        <span className="rounded-full border border-border px-2.5 py-1 text-xs font-medium">
          {candidateStatusLabel(candidate.status)}
        </span>
      </div>

      <blockquote className="mt-4 rounded-xl border border-border bg-surface-2 p-4 text-sm leading-relaxed">
        {candidate.original_text}
      </blockquote>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>{confidenceLabel(candidate.confidence_mean)}</span>
        <span>Средняя: {candidate.confidence_mean.toFixed(1)}%</span>
        <span>Минимальная: {candidate.confidence_min.toFixed(1)}%</span>
        <span>Слов: {candidate.source_word_count}</span>
      </div>

      <label className="mt-4 block">
        <span className="mb-1.5 block text-sm font-medium">Текст после проверки</span>
        <textarea
          value={editedText}
          onChange={(event) => setEditedText(event.target.value)}
          disabled={isDisabled}
          maxLength={4000}
          rows={3}
          className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm disabled:opacity-70"
        />
      </label>

      <label className="mt-3 block">
        <span className="mb-1.5 block text-sm font-medium">Заметка к проверке — необязательно</span>
        <input
          value={reviewNote}
          onChange={(event) => setReviewNote(event.target.value)}
          disabled={isDisabled}
          maxLength={500}
          className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm disabled:opacity-70"
        />
      </label>

      {candidate.reviewed_at && (
        <p className="mt-3 text-xs text-muted-foreground">
          Проверено {new Date(candidate.reviewed_at).toLocaleString("ru-RU")}
        </p>
      )}

      {!disabled && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <button
            type="button"
            disabled={isDisabled}
            onClick={() => onAction(candidate, "accept", null, reviewNote || null)}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-success/30 bg-success/10 px-3 py-2 text-sm font-medium text-success disabled:opacity-50"
          >
            <Check className="h-4 w-4" />
            {pendingAction === "accept" ? "Сохраняется…" : "Верно"}
          </button>
          <button
            type="button"
            disabled={isDisabled || editedText.trim() === candidate.original_text}
            onClick={() => onAction(candidate, "edit", editedText.trim(), reviewNote || null)}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm font-medium text-primary disabled:opacity-50"
          >
            <Pencil className="h-4 w-4" />
            {pendingAction === "edit" ? "Сохраняется…" : "Исправить"}
          </button>
          <button
            type="button"
            disabled={isDisabled}
            onClick={() => onAction(candidate, "defer", null, reviewNote || null)}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-sm font-medium text-warning disabled:opacity-50"
          >
            <Clock3 className="h-4 w-4" />
            {pendingAction === "defer" ? "Сохраняется…" : "Отложить"}
          </button>
          <button
            type="button"
            disabled={isDisabled}
            onClick={() => onAction(candidate, "reject", null, reviewNote || null)}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm font-medium text-destructive disabled:opacity-50"
          >
            <X className="h-4 w-4" />
            {pendingAction === "reject" ? "Сохраняется…" : "Исключить"}
          </button>
        </div>
      )}
    </article>
  );
}

export default function DocumentOCRReview() {
  const { documentId } = useParams<{ documentId: string }>();
  const queryClient = useQueryClient();
  const [patientNote, setPatientNote] = useState("");

  const { data: profiles, isLoading: profilesLoading } = useQuery({
    queryKey: ["health-profiles", "ocr-review"],
    queryFn: () => apiGet<HealthProfile[]>("/profiles"),
  });
  const profile = profiles?.[0] ?? null;
  const reviewKey = ["document-ocr-review", profile?.id, documentId] as const;

  const reviewQuery = useQuery({
    queryKey: reviewKey,
    queryFn: () => getOCRReview(profile!.id, documentId!),
    enabled: Boolean(profile && documentId),
  });
  const review = reviewQuery.data;

  useEffect(() => {
    setPatientNote(review?.patient_decision?.note ?? "");
  }, [review?.patient_decision?.note]);

  const candidateMutation = useMutation({
    mutationFn: ({
      candidate,
      action,
      reviewedText,
      reviewNote,
    }: {
      candidate: OCRCandidate;
      action: OCRReviewAction;
      reviewedText: string | null;
      reviewNote: string | null;
    }) =>
      reviewOCRCandidate(profile!.id, documentId!, candidate.id, {
        action,
        reviewed_text: reviewedText,
        review_note: reviewNote,
        expected_updated_at: candidate.updated_at,
      }),
    onSuccess: (next) => {
      queryClient.setQueryData<OCRReviewState>(reviewKey, next);
      toast.success("Результат проверки сохранён");
    },
    onError: (error) => toast.error(reviewErrorMessage(error)),
  });

  const patientMutation = useMutation({
    mutationFn: (decision: OCRPatientDecision) =>
      setOCRPatientDecision(profile!.id, documentId!, {
        decision,
        note: patientNote.trim() || null,
        expected_document_updated_at: review!.document_updated_at,
        expected_decision_updated_at: review!.patient_decision?.updated_at ?? null,
      }),
    onSuccess: (next) => {
      queryClient.setQueryData<OCRReviewState>(reviewKey, next);
      toast.success("Решение о пациенте сохранено");
    },
    onError: (error) => toast.error(reviewErrorMessage(error)),
  });

  const finalizeMutation = useMutation({
    mutationFn: () => finalizeOCRReview(profile!.id, documentId!, review!),
    onSuccess: (next) => {
      queryClient.setQueryData<OCRReviewState>(reviewKey, next);
      void queryClient.invalidateQueries({ queryKey: ["profile-documents", profile?.id] });
      toast.success("Проверка текста завершена");
    },
    onError: (error) => toast.error(reviewErrorMessage(error)),
  });

  if (profilesLoading || reviewQuery.isLoading) {
    return <div className="hm-card p-5 text-sm text-muted-foreground">Загрузка проверки…</div>;
  }
  if (!profile || !documentId) {
    return <div className="hm-card p-5 text-sm text-muted-foreground">Документ не найден.</div>;
  }
  if (reviewQuery.isError || !review) {
    return (
      <div className="space-y-4">
        <Link to="/app/documents" className="inline-flex items-center gap-2 text-sm text-primary">
          <ArrowLeft className="h-4 w-4" /> Назад к документам
        </Link>
        <div className="hm-card p-5 text-sm text-destructive">
          Проверка текста пока недоступна или у вас нет права её редактировать.
        </div>
      </div>
    );
  }

  const finalized = review.review_status === "finalized";
  const pendingCandidate = candidateMutation.variables?.candidate.id ?? null;
  const pendingAction = candidateMutation.variables?.action ?? null;

  return (
    <div className="space-y-6">
      <Link to="/app/documents" className="inline-flex items-center gap-2 text-sm text-primary">
        <ArrowLeft className="h-4 w-4" /> Назад к документам
      </Link>

      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">
          Проверка распознанного текста
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Исправьте только текст документа. Даже завершённая проверка не создаёт диагнозы,
          показатели анализов или другие медицинские факты автоматически.
        </p>
      </header>

      <section className="hm-card p-5 md:p-6">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div>
            <h2 className="font-display text-lg font-semibold">Состояние проверки</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Всего фрагментов: {review.candidates.length}. Нерешённых: {review.unresolved_count}.
              Отложенных: {review.deferred_count}.
            </p>
            {finalized && (
              <p className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-success">
                <CheckCircle2 className="h-4 w-4" /> Проверка завершена
                {review.finalized_at
                  ? ` ${new Date(review.finalized_at).toLocaleString("ru-RU")}`
                  : ""}
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="hm-card p-5 md:p-6">
        <div className="flex items-start gap-3">
          <UserCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-lg font-semibold">Кому принадлежит документ?</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Система не определяет пациента по распознанному тексту. Решение нужно указать явно.
            </p>
            <label className="mt-4 block">
              <span className="mb-1.5 block text-sm font-medium">Комментарий — необязательно</span>
              <input
                value={patientNote}
                onChange={(event) => setPatientNote(event.target.value)}
                disabled={finalized || patientMutation.isPending}
                maxLength={500}
                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm disabled:opacity-70"
              />
            </label>
            <div className="mt-4 grid gap-2 md:grid-cols-3">
              {(["match", "not_present", "mismatch"] as const).map((decision) => {
                const selected = review.patient_decision?.decision === decision;
                return (
                  <button
                    key={decision}
                    type="button"
                    disabled={finalized || patientMutation.isPending}
                    onClick={() => patientMutation.mutate(decision)}
                    aria-pressed={selected}
                    className={`min-h-12 rounded-xl border px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
                      selected
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border bg-background text-foreground hover:bg-surface-2"
                    }`}
                  >
                    {patientDecisionLabel(decision)}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <section className="space-y-3" aria-labelledby="ocr-candidates-heading">
        <div>
          <h2 id="ocr-candidates-heading" className="font-display text-lg font-semibold">
            Фрагменты текста
          </h2>
          <p className="text-sm text-muted-foreground">
            До завершения проверки любое решение можно изменить. Отложенный фрагмент блокирует
            финализацию.
          </p>
        </div>
        {review.candidates.map((candidate) => (
          <CandidateCard
            key={candidate.id}
            candidate={candidate}
            disabled={finalized}
            pendingAction={pendingCandidate === candidate.id ? pendingAction : null}
            onAction={(item, action, reviewedText, reviewNote) =>
              candidateMutation.mutate({
                candidate: item,
                action,
                reviewedText,
                reviewNote,
              })
            }
          />
        ))}
      </section>

      {!finalized && (
        <section className="hm-card p-5 md:p-6">
          {!review.can_finalize && (
            <div className="mb-4 flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Для завершения проверьте все фрагменты и подтвердите, что документ относится к
                этому профилю или не содержит имени пациента.
              </span>
            </div>
          )}
          <button
            type="button"
            disabled={!review.can_finalize || finalizeMutation.isPending}
            onClick={() => finalizeMutation.mutate()}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50 sm:w-auto"
          >
            <CheckCircle2 className="h-4 w-4" />
            {finalizeMutation.isPending ? "Завершение…" : "Завершить проверку текста"}
          </button>
        </section>
      )}
    </div>
  );
}
