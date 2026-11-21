"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthShell } from "@/components/auth/auth-shell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError, errorMessage, homePathFor, type Me } from "@/lib/api";

// The backend applies the real rule (its minimum length is a setting).
// These checks only save a round trip for the common mistakes.
const schema = z
  .object({
    current_password: z.string().min(1, "Enter your current password."),
    new_password: z
      .string()
      .min(8, "Use at least 8 characters.")
      .regex(/[A-Za-z]/, "Include at least 1 letter.")
      .regex(/[0-9]/, "Include at least 1 digit."),
    confirm_password: z.string(),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ["confirm_password"],
    message: "The two new passwords do not match.",
  });

type FormValues = z.infer<typeof schema>;

export default function ChangePasswordPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });

  useEffect(() => {
    let cancelled = false;
    api<Me>("/api/auth/me")
      .then((value) => {
        if (!cancelled) setMe(value);
      })
      .catch((loadError: unknown) => {
        if (cancelled) return;
        if (loadError instanceof ApiError && loadError.status === 401) router.replace("/login");
        else setError(errorMessage(loadError));
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      await api("/api/auth/change-password", {
        method: "POST",
        body: {
          current_password: values.current_password,
          new_password: values.new_password,
        },
      });
      router.replace(homePathFor({ role: me?.role ?? "VIEWER", must_change_password: false }));
    } catch (submitError) {
      setError(errorMessage(submitError));
    }
  }

  return (
    <AuthShell>
      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>
            {me?.must_change_password
              ? `You are logged in as ${me.user_id} with a password issued by the admin. Choose your own password to continue.`
              : me
                ? `Logged in as ${me.user_id}.`
                : "Loading…"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="current_password">Current password</Label>
              <Input
                id="current_password"
                type="password"
                autoComplete="current-password"
                aria-invalid={!!errors.current_password}
                {...register("current_password")}
              />
              {errors.current_password && (
                <p className="text-destructive text-sm">{errors.current_password.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="new_password">New password</Label>
              <Input
                id="new_password"
                type="password"
                autoComplete="new-password"
                aria-invalid={!!errors.new_password}
                {...register("new_password")}
              />
              <p className="text-muted-foreground text-xs">
                At least 8 characters, with at least 1 letter and 1 digit. Not your user ID.
              </p>
              {errors.new_password && (
                <p className="text-destructive text-sm">{errors.new_password.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="confirm_password">New password again</Label>
              <Input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                aria-invalid={!!errors.confirm_password}
                {...register("confirm_password")}
              />
              {errors.confirm_password && (
                <p className="text-destructive text-sm">{errors.confirm_password.message}</p>
              )}
            </div>

            <Button type="submit" className="w-full" disabled={isSubmitting || !me}>
              {isSubmitting ? "Saving…" : "Change password"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
