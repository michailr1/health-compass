export type PrimaryNavigationId = "home" | "history" | "add" | "assistant" | "more";

export interface ProductNavigationItem {
  id: PrimaryNavigationId;
  to: string;
  label: string;
  end?: boolean;
}

export interface SecondaryNavigationItem {
  to: string;
  label: string;
  description: string;
}

export const PRIMARY_NAVIGATION: ProductNavigationItem[] = [
  { id: "home", to: "/app", label: "Главная", end: true },
  { id: "history", to: "/app/history", label: "История" },
  { id: "add", to: "/app/add", label: "Добавить" },
  { id: "assistant", to: "/app/assistant", label: "Ассистент" },
  { id: "more", to: "/app/more", label: "Ещё" },
];

export const MORE_NAVIGATION: SecondaryNavigationItem[] = [
  {
    to: "/app/profile",
    label: "Профиль здоровья",
    description: "Основные данные, состояния, лекарства и другой подтверждённый контекст.",
  },
  {
    to: "/app/documents",
    label: "Анализы",
    description: "Загрузка, проверка и подтверждение результатов анализов.",
  },
  {
    to: "/app/labs",
    label: "Показатели",
    description: "Подтверждённые значения и защищённая история исправлений.",
  },
  {
    to: "/app/sleep",
    label: "Сон",
    description: "Данные сна из поддерживаемых источников, когда интеграции будут доступны.",
  },
  {
    to: "/app/sources",
    label: "Источники",
    description: "Устройства и интеграции для автоматического получения данных.",
  },
  {
    to: "/app/sign-in-methods",
    label: "Способы входа",
    description: "Управление связанными способами входа в аккаунт.",
  },
];

const LEGACY_SECONDARY_ROUTES = ["/app/genetics", "/app/plan", "/app/oura"];

export function isPrimaryNavigationActive(
  item: ProductNavigationItem,
  pathname: string,
): boolean {
  if (item.id === "home") return pathname === "/app" || pathname === "/app/";
  if (item.id === "more") {
    return (
      pathname === item.to ||
      MORE_NAVIGATION.some((secondary) => pathname.startsWith(secondary.to)) ||
      LEGACY_SECONDARY_ROUTES.some((route) => pathname.startsWith(route))
    );
  }
  return pathname === item.to || pathname.startsWith(`${item.to}/`);
}

export const ANALYSES_EMPTY_STATE_COPY =
  "Загрузите PDF или фото результатов анализов. Мы распознаем значения — вы проверите и подтвердите их, после этого они появятся в показателях, динамике и отчётах. Ничего не станет медицинским фактом без вашего подтверждения.";

export const SECURE_ANALYSES_COPY =
  "Файл хранится в зашифрованном виде и защищён от постороннего доступа. После проверки файла мы распознаем текст — вы сможете просмотреть и подтвердить результат.";

export interface DashboardPrimaryAction {
  to: string;
  label: string;
  description: string;
}

export function getEmptyDashboardPrimaryAction(uploadEnabled: boolean): DashboardPrimaryAction {
  if (uploadEnabled) {
    return {
      to: "/app/documents",
      label: "Загрузить анализы",
      description: "Добавьте PDF или фото результатов анализов, чтобы начать формировать показатели.",
    };
  }

  return {
    to: "/app/profile",
    label: "Заполнить профиль здоровья",
    description: "Начните с доступного шага: добавьте основные сведения и медицинский контекст.",
  };
}

export function isDemoDataSource(sourceLabel: string | null | undefined): boolean {
  return /(^|[^a-z])(demo|mock)([^a-z]|$)/i.test(sourceLabel ?? "");
}
