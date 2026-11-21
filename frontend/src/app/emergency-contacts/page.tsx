"use client";

import { useState } from "react";

import { Help, Notice, PickList, Section } from "@/components/apply/fields";
import { Column, PublicPage } from "@/components/public/shell";
import { useFetch } from "@/lib/use-fetch";

type Named = { id: number; name: string };
type Contact = { id: number; name: string; phone: string };

const STATEWIDE = [
  { name: "Emergency (police, fire, ambulance)", phone: "112" },
  { name: "Ambulance", phone: "108" },
];

function ContactRow({ name, phone }: { name: string; phone: string }) {
  return (
    <li className="border-portal-line flex items-center justify-between gap-3 border-b py-3 last:border-b-0">
      <span className="text-[15px] leading-snug">{name}</span>
      <a
        href={`tel:${phone.replace(/[^0-9+]/g, "")}`}
        className="text-portal-blue shrink-0 text-lg font-bold"
      >
        {phone}
      </a>
    </li>
  );
}

export default function EmergencyContactsPage() {
  const districts = useFetch<Named[]>("/api/public/districts");
  const [districtId, setDistrictId] = useState("");
  const contacts = useFetch<Contact[]>(
    districtId ? `/api/public/emergency-contacts?district_id=${districtId}` : null,
  );

  return (
    <PublicPage footer>
      <Column>
        <h1 className="text-[22px] leading-tight font-bold">Emergency contacts</h1>

        <Section title="Anywhere in Assam">
          <ul className="flex flex-col">
            {STATEWIDE.map((contact) => (
              <ContactRow key={contact.phone} {...contact} />
            ))}
          </ul>
          <Help>
            Report any accident, injury or serious emergency at once to the nearest police station
            and to 112.
          </Help>
        </Section>

        <Section title="In your district">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="contacts-district" className="text-sm font-semibold">
              District
            </label>
            <PickList
              id="contacts-district"
              value={districtId}
              onChange={setDistrictId}
              placeholder="Select district"
              options={(districts.data ?? []).map((d) => ({ value: d.id, label: d.name }))}
            />
          </div>
          {districtId && contacts.data && contacts.data.length > 0 && (
            <ul className="flex flex-col">
              {contacts.data.map((contact) => (
                <ContactRow key={contact.id} name={contact.name} phone={contact.phone} />
              ))}
            </ul>
          )}
          {districtId && contacts.data?.length === 0 && !contacts.loading && (
            <Notice tone="info">
              No district numbers are published for this district yet. Use 112 and 108.
            </Notice>
          )}
          <Help>
            Save the District Police Control Room, the nearest police station, hospital and fire
            service numbers before you leave.
          </Help>
        </Section>
      </Column>
    </PublicPage>
  );
}
