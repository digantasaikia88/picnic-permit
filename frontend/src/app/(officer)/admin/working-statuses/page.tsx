"use client";

import { MasterTable } from "@/components/admin/master-table";

export default function WorkingStatusesPage() {
  return (
    <MasterTable
      title="Working statuses"
      description="What an office can show while it holds an application, for example “Inspection scheduled”. The applicant sees it on the status page. Each office is offered only the statuses ticked for it. Every application starts as “Received”, which all three offices can use."
      noun="working status"
      endpoint="/api/admin/working-statuses"
      fields={[
        { name: "name", label: "Working status", type: "text" },
        { name: "for_dto", label: "DTO", type: "boolean", help: "Offered to the DTO" },
        {
          name: "for_police",
          label: "Police station",
          type: "boolean",
          help: "Offered to the police station",
        },
        { name: "for_dc", label: "DC office", type: "boolean", help: "Offered to the DC office" },
      ]}
    />
  );
}
