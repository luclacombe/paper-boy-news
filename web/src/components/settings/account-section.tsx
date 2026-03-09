"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { changePassword, deleteAccount } from "@/actions/account";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { AuthProvider } from "@/actions/account";

interface AccountSectionProps {
  email: string;
  authProvider: AuthProvider;
}

export function AccountSection({ email, authProvider }: AccountSectionProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // Password change state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  // Delete confirmation state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  function handleChangePassword() {
    startTransition(async () => {
      try {
        await changePassword(currentPassword, newPassword);
        setCurrentPassword("");
        setNewPassword("");
        toast.success("Password updated");
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Failed to change password"
        );
      }
    });
  }

  async function handleDeleteAccount() {
    setIsDeleting(true);
    try {
      await deleteAccount();
      const supabase = createClient();
      await supabase.auth.signOut();
      router.push("/");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to delete account"
      );
      setIsDeleting(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Email + auth provider */}
      <div>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <span className="small-caps font-headline text-xs tracking-widest text-caption">
            Email
          </span>
          <span className="font-mono text-sm text-ink">{email}</span>
        </div>
        <p className="mt-0.5 font-body text-xs italic text-caption">
          {authProvider === "google"
            ? "Signed in with Google"
            : "Signed in with email"}
        </p>
      </div>

      {/* Password change */}
      {authProvider === "email" ? (
        <div className="space-y-3">
          <span className="small-caps font-headline text-xs tracking-widest text-caption">
            Change password
          </span>
          <div className="space-y-2">
            <div className="space-y-1">
              <Label
                htmlFor="current-password"
                className="font-body text-xs text-caption"
              >
                Current password
              </Label>
              <Input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <div className="space-y-1">
              <Label
                htmlFor="new-password"
                className="font-body text-xs text-caption"
              >
                New password
              </Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
              />
            </div>
          </div>
          <Button
            onClick={handleChangePassword}
            disabled={
              isPending || !currentPassword || newPassword.length < 8
            }
            variant="outline"
            className="letterpress font-body text-sm"
          >
            {isPending ? "Updating..." : "Change password"}
          </Button>
        </div>
      ) : (
        <p className="font-body text-xs text-caption">
          Your password is managed by Google. To change it, visit your Google
          account settings.
        </p>
      )}

      {/* Delete account */}
      <div className="border-t border-rule-gray/30 pt-4">
        <p className="font-body text-xs text-caption">
          Permanently delete your account and all associated data.
        </p>

        {!showDeleteConfirm ? (
          <Button
            onClick={() => setShowDeleteConfirm(true)}
            variant="outline"
            className="mt-3 border-edition-red/40 font-body text-sm text-edition-red hover:bg-edition-red/5"
          >
            Delete account
          </Button>
        ) : (
          <div className="mt-3 space-y-3 rounded border border-edition-red/30 bg-edition-red/5 p-4">
            <p className="font-body text-xs text-ink">
              This will permanently delete your account, all your sources,
              delivery history, and stored newspapers. This cannot be undone.
            </p>
            <div className="space-y-1">
              <Label
                htmlFor="delete-confirm"
                className="font-mono text-xs text-caption"
              >
                Type DELETE to confirm
              </Label>
              <Input
                id="delete-confirm"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                placeholder="DELETE"
                autoComplete="off"
              />
            </div>
            <div className="flex gap-2">
              <Button
                onClick={handleDeleteAccount}
                disabled={deleteConfirmText !== "DELETE" || isDeleting}
                className="bg-edition-red font-body text-sm text-newsprint hover:bg-edition-red/90"
              >
                {isDeleting ? "Deleting..." : "Delete my account"}
              </Button>
              <Button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setDeleteConfirmText("");
                }}
                variant="outline"
                className="font-body text-sm"
                disabled={isDeleting}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
