"use client";

import { useMemo } from "react";
import { Controller, get, useFormContext } from "react-hook-form";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import type { FormValues } from "@/lib/apply";
import { cn } from "@/lib/utils";

// Form controls of the public pages, sized for a phone: 48 px tall, 16 px text
// (smaller text makes phone browsers zoom in on focus).

const CONTROL =
  "w-full rounded-md border border-portal-field bg-white px-3 text-base text-portal-navy " +
  "outline-none focus-visible:border-portal-blue focus-visible:ring-2 focus-visible:ring-portal-blue/30 " +
  "aria-invalid:border-portal-error disabled:bg-portal-bg disabled:text-portal-muted";

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-portal-line flex flex-col gap-4 rounded-lg border bg-white p-4">
      <h2 className="text-[17px] font-bold">{title}</h2>
      {children}
    </section>
  );
}

export function Help({ children }: { children: React.ReactNode }) {
  return <p className="text-portal-muted text-[13px] leading-snug">{children}</p>;
}

export function ErrorText({ id, children }: { id?: string; children: React.ReactNode }) {
  if (!children) return null;
  return (
    <p id={id} role="alert" className="text-portal-error text-[13px] leading-snug font-medium">
      {children}
    </p>
  );
}

export function useFieldError(name: string): string | undefined {
  const {
    formState: { errors },
  } = useFormContext<FormValues>();
  const error = get(errors, name) as { message?: string; root?: { message?: string } } | undefined;
  return error?.message ?? error?.root?.message;
}

function Shell({
  name,
  label,
  help,
  children,
}: {
  name: string;
  label: string;
  help?: React.ReactNode;
  children: React.ReactNode;
}) {
  const error = useFieldError(name);
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={name} className="text-sm font-semibold">
        {label}
      </label>
      {children}
      {help && <Help>{help}</Help>}
      <ErrorText id={`${name}-error`}>{error}</ErrorText>
    </div>
  );
}

type Name = Exclude<keyof FormValues, "members" | "documents">;

type TextProps = {
  name: Name;
  label: string;
  help?: React.ReactNode;
  type?: "text" | "tel" | "date" | "time";
  inputMode?: "numeric" | "tel" | "text";
  placeholder?: string;
  autoComplete?: string;
  maxLength?: number;
  min?: string;
  max?: string;
  uppercase?: boolean;
  /** Shown but not editable (a field that cannot be changed when correcting). */
  readOnly?: boolean;
};

export function TextInput({ name, label, help, type = "text", uppercase, ...rest }: TextProps) {
  const { register } = useFormContext<FormValues>();
  const error = useFieldError(name);
  return (
    <Shell name={name} label={label} help={help}>
      <input
        id={name}
        type={type}
        aria-invalid={!!error}
        aria-describedby={error ? `${name}-error` : undefined}
        className={cn(
          CONTROL,
          "read-only:bg-portal-bg read-only:text-portal-muted h-12",
          uppercase && "uppercase placeholder:normal-case",
        )}
        {...rest}
        {...register(name)}
      />
    </Shell>
  );
}

export function TextArea({
  name,
  label,
  help,
  autoComplete,
}: {
  name: Name;
  label: string;
  help?: React.ReactNode;
  autoComplete?: string;
}) {
  const { register } = useFormContext<FormValues>();
  const error = useFieldError(name);
  return (
    <Shell name={name} label={label} help={help}>
      <textarea
        id={name}
        rows={3}
        maxLength={500}
        autoComplete={autoComplete}
        aria-invalid={!!error}
        className={cn(CONTROL, "resize-none py-2.5")}
        {...register(name)}
      />
    </Shell>
  );
}

export function SelectInput({
  name,
  label,
  help,
  placeholder,
  options,
  disabled,
  onPick,
}: {
  name: Name;
  label: string;
  help?: React.ReactNode;
  placeholder: string;
  options: { value: string | number; label: string }[];
  disabled?: boolean;
  /** Called when the applicant picks another option. */
  onPick?: () => void;
}) {
  const { control } = useFormContext<FormValues>();
  const error = useFieldError(name);

  // The first row clears the choice, as the empty row of a plain dropdown does.
  const items = useMemo(
    () => [
      { value: "", label: placeholder },
      ...options.map((option) => ({ value: String(option.value), label: option.label })),
    ],
    [options, placeholder],
  );

  // The browser's own dropdown list cannot be sized: with a long list it runs
  // off the screen. This list opens under the field, is never taller than
  // 16 rem or the room left on screen, and scrolls inside that box.
  return (
    <Shell name={name} label={label} help={help}>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <Select
            items={items}
            value={String(field.value ?? "")}
            disabled={disabled}
            // The field counts as visited when the list closes, not when it opens,
            // so no error shows while the applicant is still choosing.
            onOpenChange={(open) => {
              if (!open) field.onBlur();
            }}
            onValueChange={(value) => {
              field.onChange(value ?? "");
              onPick?.();
            }}
          >
            <SelectTrigger
              id={name}
              ref={field.ref}
              aria-invalid={!!error}
              aria-describedby={error ? `${name}-error` : undefined}
              className={cn(
                CONTROL,
                "w-full justify-between py-0 pr-3 text-base data-[size=default]:h-12",
                !field.value && "text-portal-muted",
              )}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent
              alignItemWithTrigger={false}
              align="start"
              className="border-portal-line max-h-[min(16rem,var(--available-height))] border bg-white"
            >
              {items.map((item) => (
                <SelectItem
                  key={item.value}
                  value={item.value}
                  className={cn(
                    "data-highlighted:bg-portal-tint min-h-11 px-3 text-base",
                    !item.value && "text-portal-muted",
                  )}
                >
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
    </Shell>
  );
}

export function RadioCards({
  name,
  legend,
  options,
  columns = 1,
}: {
  name: Name;
  legend: string;
  /** `description` is a line under the label that explains the choice in plain words. */
  options: { value: string; label: string; description?: string }[];
  columns?: 1 | 2;
}) {
  const { register, watch } = useFormContext<FormValues>();
  const error = useFieldError(name);
  const current = watch(name);
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1.5 text-sm font-semibold">{legend}</legend>
      <div className={cn("grid gap-3", columns === 2 && "grid-cols-2")}>
        {options.map((option) => {
          const checked = current === option.value;
          return (
            <label
              key={option.value}
              className={cn(
                "flex min-h-12 cursor-pointer gap-3 rounded-md border px-3 py-2",
                option.description ? "items-start py-3" : "items-center",
                checked
                  ? "border-portal-blue bg-portal-tint ring-portal-blue ring-1"
                  : "border-portal-field",
              )}
            >
              <input
                type="radio"
                value={option.value}
                className={cn(
                  "accent-portal-blue size-[22px] shrink-0",
                  option.description && "mt-0.5",
                )}
                {...register(name)}
              />
              <span className="flex flex-col gap-0.5">
                <span className={cn("text-base", checked && "font-semibold")}>{option.label}</span>
                {option.description && (
                  <span className="text-portal-muted text-[13px] leading-snug">
                    {option.description}
                  </span>
                )}
              </span>
            </label>
          );
        })}
      </div>
      <ErrorText>{error}</ErrorText>
    </fieldset>
  );
}

export function Tick({ name, label }: { name: Name; label: React.ReactNode }) {
  const { register } = useFormContext<FormValues>();
  const error = useFieldError(name);
  return (
    <div className="flex flex-col gap-1">
      <label className="flex min-h-11 cursor-pointer items-start gap-3">
        <input
          type="checkbox"
          aria-invalid={!!error}
          className="accent-portal-blue mt-0.5 size-[22px] shrink-0"
          {...register(name)}
        />
        <span className="text-[15px] leading-snug">{label}</span>
      </label>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

/** A plain control outside react-hook-form, with the same look (the add-passenger form). */
export const controlClass = cn(CONTROL, "h-12");

export function PrimaryButton({ className, ...props }: React.ComponentProps<"button">) {
  return (
    <button
      type="button"
      className={cn(
        "bg-portal-blue hover:bg-portal-navy flex h-12 items-center justify-center rounded-md px-4 text-base font-semibold text-white disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function OutlineButton({ className, ...props }: React.ComponentProps<"button">) {
  return (
    <button
      type="button"
      className={cn(
        "border-portal-blue text-portal-blue hover:bg-portal-tint flex min-h-12 items-center justify-center rounded-md border bg-white px-4 py-2 text-center text-base leading-snug font-semibold disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function Notice({
  tone,
  title,
  children,
}: {
  tone: "info" | "warn" | "error";
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : undefined}
      className={cn(
        "flex flex-col gap-1 rounded-md border p-3 text-[13px] leading-snug",
        tone === "info" && "border-portal-blue bg-portal-tint text-portal-navy",
        tone === "warn" && "border-portal-warn-line bg-portal-warn-bg text-portal-warn-text",
        tone === "error" && "border-portal-error text-portal-error bg-red-50",
      )}
    >
      {title && <div className="text-sm font-bold">{title}</div>}
      <div>{children}</div>
    </div>
  );
}

/** The same confined, scrolling list as SelectInput, for use outside the application form. */
export function PickList({
  id,
  value,
  onChange,
  options,
  placeholder,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string | number; label: string }[];
  placeholder: string;
}) {
  const items = useMemo(
    () => [
      { value: "", label: placeholder },
      ...options.map((option) => ({ value: String(option.value), label: option.label })),
    ],
    [options, placeholder],
  );
  return (
    <Select items={items} value={value} onValueChange={(next) => onChange(next ?? "")}>
      <SelectTrigger
        id={id}
        className={cn(
          CONTROL,
          "w-full justify-between py-0 pr-3 text-base data-[size=default]:h-12",
          !value && "text-portal-muted",
        )}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent
        alignItemWithTrigger={false}
        align="start"
        className="border-portal-line max-h-[min(16rem,var(--available-height))] border bg-white"
      >
        {items.map((item) => (
          <SelectItem
            key={item.value}
            value={item.value}
            className={cn(
              "data-highlighted:bg-portal-tint min-h-11 px-3 text-base",
              !item.value && "text-portal-muted",
            )}
          >
            {item.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
