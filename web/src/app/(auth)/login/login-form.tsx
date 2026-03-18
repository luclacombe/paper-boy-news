"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const message = searchParams.get("message");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  // Forgot password state
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSent, setResetSent] = useState(false);

  async function handleGoogleSignIn() {
    setGoogleLoading(true);
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/api/auth/callback?next=/dashboard`,
      },
    });
    if (error) {
      setError(error.message);
      setGoogleLoading(false);
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      setError(error.message);
      setLoading(false);
    } else {
      router.push("/dashboard");
    }
  }

  async function handleForgotPassword(e: React.FormEvent) {
    e.preventDefault();
    setResetLoading(true);
    setError(null);

    const supabase = createClient();
    const { error } = await supabase.auth.resetPasswordForEmail(resetEmail, {
      redirectTo: `${window.location.origin}/api/auth/confirm`,
    });

    if (error) {
      setError(error.message);
      setResetLoading(false);
    } else {
      setResetSent(true);
      setResetLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      {message && (
        <p className="rounded-sm bg-delivered-green/10 px-4 py-3 text-center font-body text-sm text-delivered-green">
          {message}
        </p>
      )}

      {/* Google sign-in (primary) */}
      <Button
        onClick={handleGoogleSignIn}
        disabled={googleLoading}
        className="flex w-full items-center justify-center gap-2 bg-ink font-body text-sm font-semibold text-newsprint hover:bg-ink/90"
      >
        <svg className="h-4 w-4" viewBox="0 0 24 24">
          <path
            fill="currentColor"
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
          />
          <path
            fill="currentColor"
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
          />
          <path
            fill="currentColor"
            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
          />
          <path
            fill="currentColor"
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
          />
        </svg>
        {googleLoading ? "Redirecting..." : "Continue with Google"}
      </Button>

      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-rule-gray" />
        <span className="font-body text-xs text-caption">or</span>
        <div className="h-px flex-1 bg-rule-gray" />
      </div>

      {/* Email/password form */}
      <form onSubmit={handleLogin} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email" className="font-body text-sm text-ink">
            Email
          </Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            autoComplete="email"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password" className="font-body text-sm text-ink">
            Password
          </Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Your password"
            required
            autoComplete="current-password"
          />
        </div>

        {error && !showForgotPassword && (
          <p className="font-body text-sm text-edition-red">{error}</p>
        )}

        <Button
          type="submit"
          disabled={loading}
          variant="outline"
          className="w-full font-body text-sm font-semibold uppercase tracking-wider"
        >
          {loading ? "Signing in..." : "Sign In with Email"}
        </Button>
      </form>

      {/* Forgot password */}
      {!showForgotPassword ? (
        <p className="text-center font-body text-sm">
          <button
            type="button"
            onClick={() => {
              setShowForgotPassword(true);
              setResetEmail(email);
              setError(null);
            }}
            className="text-caption hover:text-ink hover:underline"
          >
            Forgot your password?
          </button>
        </p>
      ) : resetSent ? (
        <div className="rounded-sm bg-delivered-green/10 px-4 py-3 text-center">
          <p className="font-body text-sm text-delivered-green">
            Check your email for a password reset link.
          </p>
        </div>
      ) : (
        <form onSubmit={handleForgotPassword} className="space-y-3 rounded border border-rule-gray/30 p-4">
          <p className="font-body text-sm text-caption">
            Enter your email and we&apos;ll send a reset link.
          </p>
          <Input
            type="email"
            value={resetEmail}
            onChange={(e) => setResetEmail(e.target.value)}
            placeholder="you@example.com"
            required
            autoComplete="email"
          />
          {error && (
            <p className="font-body text-sm text-edition-red">{error}</p>
          )}
          <div className="flex gap-2">
            <Button
              type="submit"
              disabled={resetLoading || !resetEmail}
              variant="outline"
              className="font-body text-sm font-semibold"
            >
              {resetLoading ? "Sending..." : "Send reset link"}
            </Button>
            <Button
              type="button"
              onClick={() => {
                setShowForgotPassword(false);
                setError(null);
              }}
              variant="ghost"
              className="font-body text-sm text-caption"
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      <p className="text-center font-body text-sm text-caption">
        New here?{" "}
        <Link
          href="/onboarding"
          className="font-semibold text-ink hover:underline"
        >
          Get started
        </Link>
      </p>
    </div>
  );
}
