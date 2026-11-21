"use client";

import { MasterTable } from "@/components/admin/master-table";

export default function EmergencyContactsAdminPage() {
  return (
    <MasterTable
      title="Emergency contacts"
      description="District numbers shown on the public Emergency contacts page. 112 and 108 are always shown."
      noun="emergency contact"
      endpoint="/api/admin/emergency-contacts"
      filterByDistrict
      fields={[
        { name: "district_id", label: "District", type: "district" },
        {
          name: "name",
          label: "Service",
          type: "text",
          help: "For example District Police Control Room, Civil Hospital, Fire Station.",
        },
        { name: "phone", label: "Phone number", type: "text" },
      ]}
    />
  );
}
