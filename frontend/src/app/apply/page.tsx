import type { Metadata } from "next";

import { ApplyWizard } from "@/components/apply/wizard";

export const metadata: Metadata = {
  title: "Apply for a permit | Picnic Portal",
};

export default function ApplyPage() {
  return <ApplyWizard />;
}
