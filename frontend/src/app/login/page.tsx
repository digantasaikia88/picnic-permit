"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { RefreshCwIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthShell } from "@/components/auth/auth-shell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errorMessage, homePathFor, type Captcha, type Me } from "@/lib/api";

const schema = z.object({
  user_id: z.string().trim().min(1, "Enter your user ID."),
  password: z.string().min(1, "Enter your password."),
  captcha_answer: z.string().trim(),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const [captcha, setCaptcha] = useState<Captcha | null>(null);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    resetField,
    setError: setFieldError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { user_id: "", password: "", captcha_answer: "" },
  });

  const loadCaptcha = useCallback(async () => {
    try {
      setCaptcha(await api<Captcha>("/api/auth/captcha"));
    } catch (loadError) {
      setError(errorMessage(loadError));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api<Captcha>("/api/auth/captcha")
      .then((value) => {
        if (!cancelled) setCaptcha(value);
      })
      .catch((loadError: unknown) => {
        if (!cancelled) setError(errorMessage(loadError));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(values: FormValues) {
    setError(null);
    if (captcha?.enabled && !values.captcha_answer) {
      setFieldError("captcha_answer", { message: "Enter the text shown in the picture." });
      return;
    }
    try {
      const me = await api<Me>("/api/auth/login", {
        method: "POST",
        body: {
          user_id: values.user_id,
          password: values.password,
          captcha_id: captcha?.captcha_id,
          captcha_answer: values.captcha_answer,
        },
      });
      router.replace(homePathFor(me));
    } catch (loginError) {
      setError(errorMessage(loginError));
      // A captcha works only once, so every failed attempt needs a new one.
      resetField("captcha_answer");
      await loadCaptcha();
    }
  }

  return (
    <AuthShell>
      <Card>
        <CardHeader>
          <CardTitle>Officer login</CardTitle>
          <CardDescription>For DTO, police station, DC office and other officials.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="user_id">User ID</Label>
              <Input
                id="user_id"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                placeholder="for example dto.tinsukia"
                aria-invalid={!!errors.user_id}
                {...register("user_id")}
              />
              {errors.user_id && (
                <p className="text-destructive text-sm">{errors.user_id.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={!!errors.password}
                {...register("password")}
              />
              {errors.password && (
                <p className="text-destructive text-sm">{errors.password.message}</p>
              )}
            </div>

            {captcha?.enabled && (
              <div className="space-y-1.5">
                <Label htmlFor="captcha_answer">Type the text shown in the picture</Label>
                <div className="flex items-center gap-2">
                  {captcha.image && (
                    // eslint-disable-next-line @next/next/no-img-element -- a data URL, not a file
                    <img
                      src={captcha.image}
                      alt="Captcha text"
                      width={200}
                      height={70}
                      className="h-[52px] w-[150px] rounded-md border"
                    />
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={loadCaptcha}
                    aria-label="Show a different picture"
                    title="Show a different picture"
                  >
                    <RefreshCwIcon />
                  </Button>
                </div>
                <Input
                  id="captcha_answer"
                  autoComplete="off"
                  autoCapitalize="characters"
                  spellCheck={false}
                  aria-invalid={!!errors.captcha_answer}
                  {...register("captcha_answer")}
                />
                {errors.captcha_answer && (
                  <p className="text-destructive text-sm">{errors.captcha_answer.message}</p>
                )}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting || !captcha}>
              {isSubmitting ? "Logging in…" : "Log in"}
            </Button>
          </form>
        </CardContent>
      </Card>
      <p className="text-muted-foreground text-center text-xs">
        Forgot your password? Ask a State User Management Admin to reset it.
      </p>
    </AuthShell>
  );
}
