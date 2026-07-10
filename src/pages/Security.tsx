import { ActiveSessionsCard } from "@/components/ActiveSessionsCard";
import SignInMethodsPage from "@/pages/SignInMethods";

export default function SecurityPage() {
  return (
    <div className="space-y-6">
      <SignInMethodsPage />
      <ActiveSessionsCard />
    </div>
  );
}
