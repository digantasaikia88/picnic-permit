"use client";

import { MasterTable } from "@/components/admin/master-table";

export default function DistrictsPage() {
  return (
    <MasterTable
      title="Districts"
      description="Used for routing and jurisdiction. The short name is used in user IDs."
      noun="district"
      endpoint="/api/admin/districts"
      bulkColumns="District ID, District Name, Short Name"
      fields={[
        { name: "code", label: "District ID", type: "number" },
        { name: "name", label: "District name", type: "text" },
        {
          name: "short_name",
          label: "Short name",
          type: "text",
          help: "Lowercase letters and digits, no spaces. Used in user IDs such as dto.tinsukia. Changing it does not rename existing user IDs.",
        },
      ]}
      userFor={(row) => ({ role: "DC_OFFICE", district_id: row.id })}
      afterAddNote="This creates the DC office user. Then add the district's DTO office under DTO offices, so that applications from the district can be routed."
    />
  );
}
