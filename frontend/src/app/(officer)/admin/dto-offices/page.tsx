"use client";

import { MasterTable } from "@/components/admin/master-table";

export default function DtoOfficesPage() {
  return (
    <MasterTable
      title="DTO offices"
      description="An application is routed to the DTO office of the starting point's district."
      noun="DTO office"
      endpoint="/api/admin/dto-offices"
      bulkColumns="DTO Office ID, DTO Office Name, District ID"
      filterByDistrict
      fields={[
        { name: "code", label: "DTO Office ID", type: "text", help: "For example DTO-1022." },
        { name: "name", label: "DTO office name", type: "text" },
        { name: "district_id", label: "District", type: "district" },
      ]}
      userFor={(row) => ({ role: "DTO", dto_office_id: row.id })}
    />
  );
}
