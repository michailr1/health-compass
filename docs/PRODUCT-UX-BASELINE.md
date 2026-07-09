# Health Compass — Product & UX baseline

Версия: 1.1  
Дата: 2026-07-09  
Статус: approved target design / planned implementation

Этот документ фиксирует принятые продуктовые и интерфейсные решения из материалов Fable этапов 3, 3.5 и 2.5. Он не описывает уже реализованный функционал. Фактическое состояние находится в `CURRENT-STATE.md`.

## 1. Продуктовый фокус MVP

Первый завершённый пользовательский вертикальный срез:

```text
Login
→ Minimal Onboarding
→ Empty Dashboard
→ Upload Analysis
→ Processing
→ OCR Review
→ Lab Results
→ Metric Dynamics
→ Contextual Health Intake when needed
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
- Большая анкета не блокирует первое полезное действие.
- Медицинский контекст собирается прогрессивно и только тогда, когда он влияет на интерпретацию.
- Каждое чувствительное поле объясняет, зачем оно нужно, и остаётся опциональным.

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
- Профиль здоровья
- Настройки

`Профиль здоровья` находится в группе профиля и не конкурирует с основным CTA «Загрузить анализ». Пункт может показывать нейтральный индикатор готовности, но не тревожный счётчик.

Разделы могут скрываться до появления соответствующих данных или включения feature flag.

### Mobile bottom navigation

Не более пяти пунктов:

- Главная
- История
- Добавить
- Ассистент
- Ещё

Кнопка «Добавить» открывает контекстное меню быстрого действия: загрузить документ, добавить измерение, подключить источник. Health Profile находится в «Ещё».

## 4. Ключевые экраны MVP

### Authentication

- Login
- Google sign-in
- Email Magic Link request
- Email sent
- Auth error
- Session expired

### Minimal Onboarding

- создание первого human profile;
- имя профиля — обязательное;
- дата рождения — опционально;
- пол — опционально;
- для MVP используется одно поле «Пол», без разделения пола и гендера;
- варианты: мужской, женский, не указывать;
- минимальные обязательные согласия;
- отдельное согласие на внешний LLM;
- выбор первого действия;
- явная команда «Пропустить и заполнить позже».

Цель onboarding — быстро вывести пользователя к первому полезному действию. Он не должен превращаться в медицинскую анкету.

### Health Profile

Планируемый маршрут:

```text
/p/:profileId/health-profile
```

Экран содержит:

- имя, дату рождения и пол;
- состояния;
- аллергии;
- лекарства и добавки;
- provenance каждого значения;
- autosave и undo;
- объяснение «Почему мы спрашиваем?»;
- удаление и редактирование данных;
- нейтральную contextual readiness.

Общий процент полноты допускается только как мягкий ориентир. Основной UX сообщает, каких данных не хватает для конкретной интерпретации, а не давит требованием заполнить все поля.

### Contextual Intake Prompt

`IntakePromptCard` появляется на Metric Dynamics, в AI Assistant или другом релевантном месте только тогда, когда ответ меняет интерпретацию.

Действия:

- сохранить ответ в профиль;
- применить только к текущему анализу;
- не сейчас;
- открыть `WhyWeAskPopover`.

Один и тот же вопрос не должен назойливо повторяться в одной сессии.

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

Health Profile может показываться как ненавязчивая dismissible-подсказка и не заменяет основной CTA.

### Documents and OCR

- список документов;
- загрузка одного или нескольких файлов;
- прогресс и очередь обработки;
- document details;
- failed processing;
- OCR review с оригиналом и извлечёнными значениями;
- confidence, единицы, диапазоны и patient matching;
- save draft, confirm, cancel, delete/reprocess/download original;
- предложение добавить распознанные состояния, аллергии, лекарства или добавки в Health Profile только после подтверждения пользователя.

### Lab results and metrics

- таблица анализов;
- фильтры и поиск;
- группировка по документам и показателям;
- detail drawer;
- график динамики;
- reference band и источник нормы;
- табличный дублёр графика;
- переход к исходному документу;
- contextual intake prompt при недостатке данных;
- экспорт.

### AI Assistant

- активный profile context всегда видим;
- Fact / Interpretation / Recommendation визуально разделены;
- EvidenceBlock обязателен;
- при недостатке данных показывается отказ или точечный intake-вопрос с объяснением;
- red flag banner не содержит свободной AI-диагностики;
- пользователь может оставить feedback;
- AI не добавляет факты в Health Profile без подтверждения пользователя.

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

## 5. Progressive Health Intake

Каноническая спецификация: `PROGRESSIVE-HEALTH-INTAKE.md`.

Основные решения:

- intake — связующий UX- и data-layer, а не отдельный блокирующий домен;
- для MVP используется одно поле `sex` с пользовательским label «Пол»;
- дата рождения и пол используются для более точных референсов, но остаются опциональными;
- беременность/лактация и иные клинические уточнения спрашиваются контекстно;
- этническая принадлежность не входит в обычный MVP intake и может запрашиваться только конкретным валидированным правилом;
- состояния, аллергии, лекарства и добавки могут поступать из OCR только после human confirmation;
- intake не является самодиагностикой.

## 6. Дополнительные функции

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
- полноценный Pet Health;
- lifestyle intake;
- семейный анамнез.

## 7. Human и Pet design separation

- Human accent: `#0E7490`.
- Pet accent: `#7C5CBF`.
- На каждом pet-экране обязателен `PetHeader` с именем, видом и контекстом питомца.
- Human и Pet используют разные prompts, retrieval indices и norm dictionaries.
- Pet-данные не отображаются внутри Human AI context и наоборот.
- Human Health Profile недоступен в pet-контексте; Pet intake проектируется отдельно.

## 8. Компонентный baseline

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
- `HealthProfileForm`
- `IntakePromptCard`
- `CompletenessMeter`
- `WhyWeAskPopover`
- `UndoSnackbar`

## 9. UI states

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

Health Profile дополнительно имеет `saving`, `saved` и `read-only` states. Intake Prompt поддерживает `answered`, `not now` и `why we ask` states.

Кнопки без описанного действия, disabled-state и error-state не допускаются.

## 10. Accessibility

- WCAG 2.1 AA;
- клавиатурная навигация и видимый focus;
- статус не кодируется только цветом;
- tap targets не менее 44×44 px;
- графики имеют табличную альтернативу;
- поддерживается reduced motion;
- печатные отчёты используют A4 layout.

## 11. Ближайший frontend порядок

1. AppShell, design tokens и Human/Pet theme context.
2. Auth UI и session-expired state.
3. Minimal Onboarding, Health Profile entry point и Empty Dashboard.
4. Health Profile form, autosave, provenance и readiness.
5. Upload и processing queue.
6. OCR Review с autosave и подтверждённым импортом фактов.
7. Lab Results, Metric Dynamics и IntakePromptCard.
8. AI Assistant с обязательным EvidenceBlock.
9. Doctor Report.
10. Settings, sessions, privacy, export/delete.
11. Attention Inbox, search и notifications.

## 12. Правило реализации

- Этот baseline задаёт целевой UX, но не подтверждает наличие backend API.
- Для каждого экрана до разработки проверяются API dependencies и permissions.
- Реализация не может ослаблять `SECURITY-INVARIANTS.md` и `AI-PRODUCT-SAFETY.md`.
- Health intake должен соответствовать `PROGRESSIVE-HEALTH-INTAKE.md`.
- Отклонение от baseline фиксируется ADR или обновлением этого документа.
