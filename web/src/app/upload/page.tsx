import RequireAuth from "@/components/RequireAuth";
import { UploadPageContent } from "./_content";

export default function UploadPage() {
  return (
    <RequireAuth>
      <UploadPageContent />
    </RequireAuth>
  );
}
