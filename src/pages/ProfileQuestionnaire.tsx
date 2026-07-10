import { useQuery } from "@tanstack/react-query";

import { ProfileCompletionCard } from "@/components/ProfileCompletionCard";
import { apiGet, type HealthProfile } from "@/lib/api";
import HealthProfilePage from "@/pages/HealthProfile";

export default function ProfileQuestionnairePage() {
  const { data: profiles } = useQuery({
    queryKey: ["profiles-for-completion"],
    queryFn: () => apiGet<HealthProfile[]>("/profiles"),
  });
  const profile = profiles?.[0];

  return (
    <div className="space-y-6">
      {profile && <ProfileCompletionCard profileId={profile.id} />}
      <HealthProfilePage />
    </div>
  );
}
