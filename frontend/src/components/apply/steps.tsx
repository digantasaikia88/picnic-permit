"use client";

import { useState } from "react";
import { useFieldArray, useFormContext } from "react-hook-form";

import {
  controlClass,
  ErrorText,
  Help,
  Notice,
  OutlineButton,
  RadioCards,
  Section,
  SelectInput,
  TextArea,
  TextInput,
  Tick,
  useFieldError,
} from "@/components/apply/fields";
import { UploadRow } from "@/components/apply/upload-row";
import {
  countPeople,
  DRIVER_TICKS,
  formatDay,
  GENDERS,
  VEHICLE_TICKS,
  type FormConfig,
  type FormValues,
} from "@/lib/apply";
import { useFetch } from "@/lib/use-fetch";

type Named = { id: number; name: string };

function clock(hour: number): string {
  return `${hour % 12 === 0 ? 12 : hour % 12}:00 ${hour < 12 ? "AM" : "PM"}`;
}

function genderLabel(value: string): string {
  return GENDERS.find((gender) => gender.value === value)?.label ?? "";
}

/** Registered seating capacity: whole numbers from 1 to 100. */
const SEAT_OPTIONS = Array.from({ length: 100 }, (_unused, index) => ({
  value: index + 1,
  label: String(index + 1),
}));

function options(rows: Named[] | undefined) {
  return (rows ?? []).map((row) => ({ value: row.id, label: row.name }));
}

// -------------------------------------------------------------------- step 1

export function StepLeaderAndJourney({
  config,
  locked,
}: {
  config: FormConfig;
  /** A correction: the mobile number is fixed, and for the applicant the starting district too. */
  locked?: "applicant" | "officer";
}) {
  const { watch, setValue } = useFormContext<FormValues>();
  const districtId = watch("origin_district_id");
  const districts = useFetch<Named[]>("/api/public/districts");
  const stations = useFetch<Named[]>(
    districtId ? `/api/public/police-stations?district_id=${districtId}` : null,
  );

  return (
    <>
      <Section title="Group leader">
        <TextInput name="leader_name" label="Full name" autoComplete="name" maxLength={100} />
        <div className="grid grid-cols-2 gap-3">
          <TextInput
            name="leader_age"
            label="Age"
            inputMode="numeric"
            maxLength={3}
            help={`At least ${config.leader_min_age} years`}
          />
          <SelectInput
            name="leader_gender"
            label="Gender"
            placeholder="Select"
            options={[...GENDERS]}
          />
        </div>
        <TextInput
          name="leader_mobile"
          label="Mobile number"
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          maxLength={10}
          readOnly={Boolean(locked)}
          help={
            locked
              ? "The mobile number cannot be changed, because the OTP is tied to it."
              : "Verified by OTP when you submit. Status updates are sent to this number by SMS, and the permit is downloaded with an OTP to it."
          }
        />
      </Section>

      <Section title="Journey">
        <TextInput
          name="travel_date"
          label="Date of travel"
          type="date"
          min={config.min_travel_date}
          max={config.max_travel_date}
          help={
            <>
              Must be at least {config.min_days_before_travel} days and not more than{" "}
              {config.max_days_before_travel} days from today
              {config.season.start_date && config.season.end_date && (
                <>
                  , within the picnic season ({formatDay(config.season.start_date)} to{" "}
                  {formatDay(config.season.end_date)})
                </>
              )}
              . You can choose {formatDay(config.min_travel_date)} to{" "}
              {formatDay(config.max_travel_date)}.
            </>
          }
        />
        <div className="grid grid-cols-2 gap-3">
          <TextInput name="departure_time" label="Departure time" type="time" />
          <TextInput name="return_time" label="Return time" type="time" />
        </div>
        <Help>
          Departure not before {clock(config.earliest_departure_hour)}. The group must be back home
          by {clock(config.latest_return_hour)}.
        </Help>
        <TextArea name="origin_address" label="Starting point (full address)" />
        <SelectInput
          name="origin_district_id"
          label="District of starting point"
          placeholder="Select district"
          options={options(districts.data)}
          // A police station belongs to a district: another district clears it.
          onPick={() => setValue("origin_police_station_id", "")}
          disabled={locked === "applicant"}
          help={
            locked === "applicant"
              ? "The district cannot be changed. If it is wrong, tell the office that returned the application."
              : locked === "officer"
                ? "If you change the district, the application moves to the DTO of the new district."
                : undefined
          }
        />
        <SelectInput
          name="origin_police_station_id"
          label="Police station of starting point"
          placeholder={districtId ? "Select police station" : "Select the district first"}
          options={options(stations.data)}
          disabled={!districtId}
          help="Shows the stations of the selected district. This station will verify your application."
        />
      </Section>
    </>
  );
}

// -------------------------------------------------------------------- step 2

export function StepDestination() {
  const { watch, setValue } = useFormContext<FormValues>();
  const districtId = watch("destination_district_id");
  const band = watch("driving_band");
  const districts = useFetch<Named[]>("/api/public/districts");
  const stations = useFetch<Named[]>(
    districtId ? `/api/public/police-stations?district_id=${districtId}` : null,
  );

  return (
    <>
      <Section title="Picnic spot">
        <Help>Only one picnic spot is allowed per trip.</Help>
        <TextArea name="destination_address" label="Full address of the picnic spot" />
        <SelectInput
          name="destination_district_id"
          label="District"
          placeholder="Select district"
          options={options(districts.data)}
          onPick={() => setValue("destination_police_station_id", "")}
        />
        <SelectInput
          name="destination_police_station_id"
          label="Police station (optional)"
          placeholder="Not sure"
          options={options(stations.data)}
          disabled={!districtId}
          help="Leave as “Not sure” if you do not know it. The police will fill it in during verification."
        />
      </Section>

      <Section title="Driving time, one way">
        <RadioCards
          name="driving_band"
          legend="From the starting point to the picnic spot"
          options={[
            { value: "UP_TO_60", label: "Up to 60 minutes" },
            { value: "FROM_60_TO_90", label: "60 to 90 minutes" },
          ]}
        />
        {band === "FROM_60_TO_90" && (
          <Notice tone="warn" title="Needs specific approval">
            A destination 60 to 90 minutes away is considered only with the specific approval of the
            District Commissioner.
          </Notice>
        )}
        <Help>Journeys of more than 90 minutes are not permitted and cannot be applied for.</Help>
      </Section>
    </>
  );
}

// -------------------------------------------------------------------- step 3

export function StepVehicle({ config }: { config: FormConfig }) {
  const vehicleDocuments = config.documents.filter((rule) => rule.doc_type !== "DRIVING_LICENCE");

  return (
    <>
      <Section title="Vehicle details">
        <TextInput
          name="vehicle_reg_number"
          label="Registration number"
          placeholder="AS01 AB 1234"
          maxLength={20}
          uppercase
        />
        <SelectInput
          name="vehicle_type_id"
          label="Type of vehicle"
          placeholder="Select type"
          options={options(config.vehicle_types)}
          help="Goods vehicles, trucks, tractors and trailers cannot carry picnic passengers."
        />
        <RadioCards
          name="vehicle_usage"
          legend="Private or hired"
          options={[
            {
              value: "PRIVATE",
              label: "Private",
              description:
                "The vehicle belongs to the group leader or someone in the group, such as a family’s own car, and is not being paid for.",
            },
            {
              value: "HIRED",
              label: "Hired Transport Vehicle",
              description:
                "The vehicle is taken on hire for the trip, such as a bus, traveller or taxi from an operator, usually with its driver.",
            },
          ]}
        />
        <SelectInput
          name="seating_capacity"
          label="Registered seating capacity"
          placeholder="Select"
          options={SEAT_OPTIONS}
          help="As printed on the Registration Certificate. You cannot add more people than this in Step 5."
        />
        <TextInput name="owner_name" label="Owner’s name" maxLength={100} />
        <TextInput
          name="owner_mobile"
          label="Owner’s mobile number"
          type="tel"
          inputMode="numeric"
          maxLength={10}
        />
      </Section>

      <Section title="Vehicle documents">
        <Help>
          PDF or photo, up to {config.upload_max_mb} MB each. The DTO will check these against the
          originals.
        </Help>
        <div>
          {vehicleDocuments.map((rule) => (
            <UploadRow
              key={rule.doc_type}
              rule={rule}
              maxMb={config.upload_max_mb}
              help={
                rule.doc_type === "INSPECTION_CERTIFICATE"
                  ? "If you do not upload this, the vehicle must be brought to the DTO office for inspection."
                  : undefined
              }
            >
              {rule.doc_type === "OWNER_SELF_CERTIFICATE" && (
                <p className="text-[13px] leading-snug">
                  <a
                    href="/owner-self-certificate.pdf"
                    download="Owner-Self-Certificate.pdf"
                    className="text-portal-blue font-semibold underline"
                  >
                    Download the self-certificate form (PDF)
                  </a>
                  <span className="text-portal-muted">
                    . Print it, have the vehicle owner fill and sign it, then scan or photograph it
                    and upload it here.
                  </span>
                </p>
              )}
            </UploadRow>
          ))}
        </div>
      </Section>

      <Section title="Confirm">
        {VEHICLE_TICKS.map((item) => (
          <Tick key={item.name} name={item.name} label={item.label} />
        ))}
      </Section>
    </>
  );
}

// -------------------------------------------------------------------- step 4

export function StepDriver({ config }: { config: FormConfig }) {
  const { watch } = useFormContext<FormValues>();
  const hasHandyman = watch("has_handyman");
  const licence = config.documents.find((rule) => rule.doc_type === "DRIVING_LICENCE");

  return (
    <>
      <Section title="Driver">
        <TextInput name="driver_name" label="Full name" maxLength={100} />
        <TextInput name="licence_number" label="Driving licence number" maxLength={25} uppercase />
        <TextInput
          name="licence_class"
          label="Vehicle class on the licence"
          placeholder="LMV, Transport, HPMV"
          maxLength={60}
          help="The licence must cover the type of vehicle chosen in Step 3."
        />
        <TextInput
          name="licence_valid_until"
          label="Licence valid until"
          type="date"
          help="The licence must be valid on the date of travel."
        />
        <TextInput
          name="driver_mobile"
          label="Mobile number"
          type="tel"
          inputMode="numeric"
          maxLength={10}
        />
        {licence && (
          <div className="border-portal-line border-t">
            <UploadRow rule={licence} maxMb={config.upload_max_mb} />
          </div>
        )}
      </Section>

      <Section title="Confirm about the driver">
        {DRIVER_TICKS.map((item) => (
          <Tick key={item.name} name={item.name} label={item.label} />
        ))}
      </Section>

      <Section title="Handyman">
        <Tick name="has_handyman" label="A handyman will travel with the vehicle" />
        {hasHandyman && (
          <>
            <TextInput name="handyman_name" label="Handyman’s name" maxLength={100} />
            <TextInput
              name="handyman_mobile"
              label="Handyman’s mobile number"
              type="tel"
              inputMode="numeric"
              maxLength={10}
            />
          </>
        )}
      </Section>
    </>
  );
}

// -------------------------------------------------------------------- step 5

const EMPTY_PASSENGER = { name: "", age: "", gender: "" };

export function StepPassengers({
  config,
  onEditLeader,
}: {
  config: FormConfig;
  onEditLeader: () => void;
}) {
  const { control, watch, clearErrors } = useFormContext<FormValues>();
  const { fields, append, update, remove } = useFieldArray({ control, name: "members" });
  const values = watch();
  const capacityError = useFieldError("members");

  const [draft, setDraft] = useState(EMPTY_PASSENGER);
  const [editing, setEditing] = useState<number | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);

  const capacity = /^[0-9]+$/.test(values.seating_capacity) ? Number(values.seating_capacity) : 0;
  const used = countPeople(values, config.child_free_below_age);
  const left = Math.max(0, capacity - used);
  const canAdd = editing !== null || left > 0;

  const crew = values.has_handyman ? "the driver and the handyman" : "the driver";
  const memberCount = values.members.length;

  function save() {
    const name = draft.name.trim();
    if (!name) return setDraftError("Enter the passenger's full name.");
    if (!/^[0-9]+$/.test(draft.age) || Number(draft.age) > 120) {
      return setDraftError("Enter the age in years.");
    }
    if (!draft.gender) return setDraftError("Choose the gender.");

    const passenger = { name, age: draft.age, gender: draft.gender };
    if (editing === null) append(passenger);
    else update(editing, passenger);
    setDraft(EMPTY_PASSENGER);
    setEditing(null);
    setDraftError(null);
    clearErrors("members");
  }

  return (
    <>
      <div className="border-portal-blue bg-portal-tint flex flex-col gap-1 rounded-lg border px-4 py-3.5">
        <div className="text-[13px] font-semibold">Seats used</div>
        <div className="text-[26px] font-bold" aria-live="polite">
          {used} of {capacity || "?"}
        </div>
        <p className="text-[13px] leading-snug">
          The group leader, {memberCount} {memberCount === 1 ? "member" : "members"}, {crew}. You
          cannot add more people than the seating capacity of the vehicle.
          {config.child_free_below_age > 0 &&
            ` Children below ${config.child_free_below_age} years are not counted.`}
        </p>
      </div>
      <ErrorText>{capacityError}</ErrorText>

      <Section title={`Passengers added (${memberCount + 1})`}>
        <ol className="flex flex-col">
          <li className="border-portal-line flex min-h-[60px] items-center gap-2.5 border-b">
            <span className="text-portal-muted w-[22px] text-sm font-semibold">1</span>
            <span className="flex min-w-0 grow flex-col gap-0.5">
              <span className="truncate text-[15px] font-semibold">
                {values.leader_name || "Group leader"}
              </span>
              <span className="text-portal-muted text-[13px]">
                Group leader · {values.leader_age || "?"} years, {genderLabel(values.leader_gender)}
              </span>
            </span>
            <button
              type="button"
              onClick={onEditLeader}
              className="text-portal-blue h-11 px-1.5 text-sm font-semibold"
            >
              Edit
            </button>
          </li>
          {fields.map((field, index) => (
            <li
              key={field.id}
              className="border-portal-line flex min-h-[60px] items-center gap-2.5 border-b last:border-b-0"
            >
              <span className="text-portal-muted w-[22px] text-sm font-semibold">{index + 2}</span>
              <span className="flex min-w-0 grow flex-col gap-0.5">
                <span className="truncate text-[15px] font-semibold">{field.name}</span>
                <span className="text-portal-muted text-[13px]">
                  Member · {field.age} years, {genderLabel(field.gender)}
                </span>
              </span>
              <button
                type="button"
                className="text-portal-blue h-11 px-1.5 text-sm font-semibold"
                onClick={() => {
                  setDraft({ name: field.name, age: field.age, gender: field.gender });
                  setEditing(index);
                  setDraftError(null);
                }}
              >
                Edit
              </button>
              <button
                type="button"
                className="text-portal-blue h-11 px-1.5 text-sm font-semibold"
                onClick={() => {
                  remove(index);
                  if (editing !== null) {
                    setEditing(null);
                    setDraft(EMPTY_PASSENGER);
                  }
                  clearErrors("members");
                }}
              >
                Remove
              </button>
            </li>
          ))}
        </ol>
      </Section>

      <Section title={editing === null ? "Add a passenger" : `Edit passenger ${editing + 2}`}>
        {!capacity ? (
          <Help>Enter the registered seating capacity in Step 3 first.</Help>
        ) : !canAdd ? (
          <Notice tone="info">
            The registered seating capacity is reached. No more passengers can be added.
          </Notice>
        ) : (
          <>
            {editing === null && (
              <Help>
                {left} {left === 1 ? "seat" : "seats"} left. This form closes when the registered
                seating capacity is reached.
              </Help>
            )}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="passenger-name" className="text-sm font-semibold">
                Full name
              </label>
              <input
                id="passenger-name"
                className={controlClass}
                maxLength={100}
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="passenger-age" className="text-sm font-semibold">
                  Age
                </label>
                <input
                  id="passenger-age"
                  className={controlClass}
                  inputMode="numeric"
                  maxLength={3}
                  value={draft.age}
                  onChange={(event) => setDraft({ ...draft, age: event.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="passenger-gender" className="text-sm font-semibold">
                  Gender
                </label>
                <select
                  id="passenger-gender"
                  className={controlClass}
                  value={draft.gender}
                  onChange={(event) => setDraft({ ...draft, gender: event.target.value })}
                >
                  <option value="">Select</option>
                  {GENDERS.map((gender) => (
                    <option key={gender.value} value={gender.value}>
                      {gender.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <ErrorText>{draftError}</ErrorText>
            <div className="flex gap-3">
              {editing !== null && (
                <OutlineButton
                  onClick={() => {
                    setEditing(null);
                    setDraft(EMPTY_PASSENGER);
                    setDraftError(null);
                  }}
                >
                  Cancel
                </OutlineButton>
              )}
              <OutlineButton className="grow" onClick={save}>
                {editing === null ? "Add to list" : "Save changes"}
              </OutlineButton>
            </div>
          </>
        )}
      </Section>

      <Help>
        The group leader is added automatically from Step 1 and cannot be removed. Only the people
        listed here may travel in the vehicle.
      </Help>
    </>
  );
}
