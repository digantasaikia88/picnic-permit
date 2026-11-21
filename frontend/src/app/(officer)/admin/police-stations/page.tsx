"use client";

import { MasterTable } from "@/components/admin/master-table";

export default function PoliceStationsPage() {
  return (
    <MasterTable
      title="Police stations"
      description="Shown in the origin and destination dropdowns of the selected district."
      noun="police station"
      endpoint="/api/admin/police-stations"
      bulkColumns="Police Station Name, District ID"
      filterByDistrict
      fields={[
        {
          name: "name",
          label: "Police station name",
          type: "text",
          help: "Must be unique within the district, for example Margherita PS.",
        },
        {
          name: "district_id",
          label: "District",
          type: "district",
          help: "Moving a station to another district affects new applications only.",
        },
      ]}
      userFor={(row) => ({ role: "POLICE_STATION", police_station_id: row.id })}
    />
  );
}
