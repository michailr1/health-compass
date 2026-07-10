import { useQuery } from "@tanstack/react-query";

import { ProfileCompletionCard } from "@/components/ProfileCompletionCard";
import { apiGet, type HealthProfile } from "@/lib/api";
import HealthProfilePage from "@/pages/HealthProfile";
import "@/styles/clinical-context-mobile.css";

const CLINICAL_SECTIONS = [
  { href: "#clinical-conditions", label: "Состояния" },
  { href: "#clinical-allergies", label: "Аллергии" },
  { href: "#clinical-medications", label: "Лекарства" },
  { href: "#clinical-supplements", label: "Добавки" },
];

export default function ProfileQuestionnairePage() {
  const { data: profiles } = useQuery({
    queryKey: ["profiles-for-completion"],
    queryFn: () => apiGet<HealthProfile[]>("/profiles"),
  });
  const profile = profiles?.[0];

  return (
    <div className="clinical-questionnaire space-y-6">
      {profile && <ProfileCompletionCard profileId={profile.id} />}
      <nav className="clinical-section-nav" aria-label="Разделы клинического контекста">
        {CLINICAL_SECTIONS.map((item) => (
          <a key={item.href} href={item.href}>{item.label}</a>
        ))}
      </nav>
      <div id="basic-profile" className="scroll-mt-24">
        <HealthProfilePage />
      </div>
    </div>
  );
}
