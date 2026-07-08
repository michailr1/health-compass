# Health Compass — Product & UX baseline

Версия: 1.0  
Дата: 2026-07-09  
Статус: approved target design / planned implementation

Этот документ фиксирует принятые продуктовые и интерфейсные решения из материалов Fable этапов 3 и 3.5. Он не описывает уже реализованный функционал. Фактическое состояние находится в `CURRENT-STATE.md`.

## 1. Продуктовый фокус MVP

Первый завершённый пользовательский вертикальный срез:

```text
Login
→ Onboarding
→ Empty Dashboard
→ Upload Analysis
→ Processing
→ OCR Review
→ Lab Results
→ Metric Dynamics
→ AI Explanation with Evidence
→ Doctor Report
```

Human Health реализуется первым. Pet Health проектируется как отдельный future-ready контур и не блокирует Human MVP.

## 2. Основные продуктовые принципы

- Интерфейс должен помогать пользователю понять состояние данных, а не имитировать медицинскую диагностику.
- Реальные, демонстрационные, извлечённые и AI-интерпретированные данные визуально различаются.
- OCR-результат не становится подтверждённым медицинским фактом без проверки пользователем.
- Каждое содержательное AI-объяснение показывает evidence и provenance.
- Красный используется только для подтверждённых red flags и критичных destructive actions.
- Экспорт и удаление данных доступны из настроек и не скрываются за обращением в поддержку.
- Human и Pet контуры нельзя перепутать ни визуально, ни в навигации, ни в AI-контексте.

## 3. Навигация MVP

### Desktop sidebar

- Главная
- История
- Анализы
- Документы
- Показатели
- Oura
- Ассистент
- Отчёты
- Настройки

Разделы могут скрываться до появления соответствующих данных или включения feature flag.

### Mobile bottom navigation

Не более пяти пунктов:

- Главная
- История
- Добавить
- Ассистент
- Ещё

Кнопка «Добавить» открывает контекстное меню быстрого действия: загрузить документ, добавить измерение, подключить источник.

## 4. Ключевые экраны MVP

### Authentication

- Login
- Google sign-in
- Email Magic Link request
- Email sent
- Auth error
- Session expired

### Onboarding

- создание первого human profile;
- минимальные обязательные согласия;
- отдельное согласие на внешний LLM;
- выбор первого действия.

### Dashboard

Состояния:

- empty;
- with data;
- needs attention;
- partial/stale data;
- loading/error.

Основные CTA пустого состояния:

- «Загрузить анализ»;
- «Подключить Oura»;
- «Добавить измерение».

### Documents and OCR

- список документов;
- загрузка одного или нескольких файлов;
- прогресс и очередь обработки;
- document details;
- failed processing;
- OCR review с оригиналом и извлечёнными значениями;
- confidence, единицы, диапазоны и patient matching;
- save draft, confirm, cancel, delete/reprocess/download original.

### Lab results and metrics

- таблица анализов;
- фильтры и поиск;
- группировка по документам и показателям;
- detail drawer;
- график динамики;
- reference band и источник нормы;
- табличный дублёр графика;
- переход к исходному документу;
- экспорт.

### AI Assistant

- активный profile context всегда видим;
- Fact / Interpretation / Recommendation визуально разделены;
- EvidenceBlock обязателен;
- при недостатке данных показывается отказ с объяснением;
- red flag banner не содержит свободной AI-диагностики;
- пользователь может оставить feedback.

### Doctor Report

- выбор периода и разделов;
- preview;
- редактируемые вопросы врачу;
- evidence и provenance;
- A4 print layout;
- PDF export.

### Settings

- профиль;
- identities;
- активные сессии;
- consents;
- integrations;
- notifications;
- export;
- delete account/profile;
- audit and privacy.

## 5. Дополнительные функции

### MVP candidates

- Attention Inbox: документы на проверку, ошибки синхронизации, просроченные действия.
- Autosave OCR draft и восстановление после обрыва.
- Data freshness and sync status.
- Global search по документам, показателям и временной шкале.
- Notification center без передачи медицинских значений в product analytics.
- Session management и отзыв отдельных сессий.
- Bulk upload с очередью и понятной обработкой ошибок.

### Post-MVP / deferred

- Offline Emergency Card;
- caregiver mode;
- profile transfer;
- расширенный command palette;
- сложные bulk actions;
- conflict resolution между источниками;
- clinician workflows;
- billing;
- полноценный Pet Health.

## 6. Human и Pet design separation

- Human accent: `#0E7490`.
- Pet accent: `#7C5CBF`.
- На каждом pet-экране обязателен `PetHeader` с именем, видом и контекстом питомца.
- Human и Pet используют разные prompts, retrieval indices и norm dictionaries.
- Pet-данные не отображаются внутри Human AI context и наоборот.

## 7. Компонентный baseline

Основные компоненты:

- `AppShell`
- `Sidebar`
- `MobileNavigation`
- `ProfileSwitcher`
- `HumanHeader`
- `PetHeader`
- `StatCard`
- `AttentionCard`
- `TrendChart`
- `ReferenceBandChart`
- `Timeline`
- `TimelineItem`
- `DocumentCard`
- `UploadDropzone`
- `ProcessingStatus`
- `ExtractReviewTable`
- `ConfidenceBadge`
- `FactBadge`
- `InterpretationBadge`
- `RecommendationBadge`
- `EvidenceBlock`
- `RedFlagBanner`
- `EmptyState`
- `ErrorState`
- `ConnectionStatus`
- `ConsentDialog`
- `DoctorReport`
- `EmergencyCard`
- `DataSourceBadge`
- `ProvenancePopover`

## 8. UI states

Каждый экран и action должны иметь явные состояния:

- empty;
- loading;
- processing;
- success;
- needs review;
- partial data;
- stale data;
- permission denied;
- validation error;
- backend error;
- network error;
- integration disconnected;
- mobile narrow screen.

Кнопки без описанного действия, disabled-state и error-state не допускаются.

## 9. Accessibility

- WCAG 2.1 AA;
- клавиатурная навигация и видимый focus;
- статус не кодируется только цветом;
- tap targets не менее 44×44 px;
- графики имеют табличную альтернативу;
- поддерживается reduced motion;
- печатные отчёты используют A4 layout.

## 10. Ближайший frontend порядок

1. AppShell, design tokens и Human/Pet theme context.
2. Auth UI и session-expired state.
3. Onboarding и Empty Dashboard.
4. Upload и processing queue.
5. OCR Review с autosave.
6. Lab Results и Metric Dynamics.
7. AI Assistant с обязательным EvidenceBlock.
8. Doctor Report.
9. Settings, sessions, privacy, export/delete.
10. Attention Inbox, search и notifications.

## 11. Правило реализации

- Этот baseline задаёт целевой UX, но не подтверждает наличие backend API.
- Для каждого экрана до разработки проверяются API dependencies и permissions.
- Реализация не может ослаблять `SECURITY-INVARIANTS.md` и `AI-PRODUCT-SAFETY.md`.
- Отклонение от baseline фиксируется ADR или обновлением этого документа.
