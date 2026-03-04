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

  return (
    <form onSubmit={handleLogin} className="space-y-4">
      {message && (
        <p className="rounded-sm bg-delivered-green/10 px-4 py-3 text-center font-body text-sm text-delivered-green">
          {message}
        </p>
      )}

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

      {error && (
        <p className="font-body text-sm text-edition-red">{error}</p>
      )}

      <Button
        type="submit"
        disabled={loading}
        className="w-full bg-ink font-body text-sm font-semibold uppercase tracking-wider text-newsprint hover:bg-ink/90"
      >
        {loading ? "Signing in..." : "Sign In"}
      </Button>

      <p className="text-center font-body text-sm text-caption">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="font-semibold text-ink hover:underline">
          Sign up
        </Link>
      </p>
    </form>
  );
}
