"use client";

import { MasterTable } from "@/components/admin/master-table";

export default function VehicleTypesPage() {
  return (
    <MasterTable
      title="Vehicle types"
      description="Offered in Step 3 of the application form. Never add goods vehicles, trucks, tractors or trailers: the SOP excludes them."
      noun="vehicle type"
      endpoint="/api/admin/vehicle-types"
      fields={[{ name: "name", label: "Vehicle type", type: "text" }]}
    />
  );
}
