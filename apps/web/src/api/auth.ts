import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { MeOut, MfaRequiredOut, SessionOut, TotpSetupOut, UserOut } from "./types";

export type Credentials = { email: string; password: string };
export type LoginResult = SessionOut | MfaRequiredOut;

export function isMfaRequired(r: LoginResult): r is MfaRequiredOut {
  return "mfa_token" in r;
}

export const meKey = ["me"] as const;

export function useMe() {
  return useQuery({ queryKey: meKey, queryFn: () => api<MeOut>("/me"), retry: false });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Credentials) => api<LoginResult>("/auth/login", { method: "POST", body }),
    onSuccess: (r) => {
      // Drop the cached "signed out" answer so the guard waits for a fresh /me.
      if (!isMfaRequired(r)) qc.removeQueries({ queryKey: meKey });
    },
  });
}

export function useLoginMfa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { mfa_token: string; code: string }) =>
      api<SessionOut>("/auth/login/mfa", { method: "POST", body }),
    onSuccess: () => qc.removeQueries({ queryKey: meKey }),
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (body: Credentials) => api<UserOut>("/auth/register", { method: "POST", body }),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/auth/logout", { method: "POST" }),
    onSettled: () => {
      qc.clear();
    },
  });
}

export function useTotpSetup() {
  return useMutation({ mutationFn: () => api<TotpSetupOut>("/auth/totp/setup", { method: "POST" }) });
}

export function useTotpEnable() {
  return useMutation({
    mutationFn: (code: string) => api<void>("/auth/totp/enable", { method: "POST", body: { code } }),
  });
}
