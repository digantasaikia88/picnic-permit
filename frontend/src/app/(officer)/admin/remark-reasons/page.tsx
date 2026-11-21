"use client";

import { MasterTable } from "@/components/admin/master-table";

export default function RemarkReasonsPage() {
  return (
    <div className="space-y-10">
      <MasterTable
        title="Reasons for returning an application"
        description="Ready reasons an officer can pick when returning an application to the applicant. The applicant sees the reason chosen."
        noun="reason"
        endpoint="/api/admin/remark-reasons"
        listQuery="kind=RETURN"
        createExtra={{ kind: "RETURN" }}
        fields={[{ name: "name", label: "Reason for return", type: "text" }]}
      />
      <MasterTable
        title="Reasons for rejecting an application"
        description="Ready reasons an officer can pick when rejecting an application. The applicant sees the reason chosen."
        noun="reason"
        endpoint="/api/admin/remark-reasons"
        listQuery="kind=REJECT"
        createExtra={{ kind: "REJECT" }}
        fields={[{ name: "name", label: "Reason for rejection", type: "text" }]}
      />
    </div>
  );
}
