"use client";

import { useState } from "react";
import { useGoogleLogin, googleLogout } from "@react-oauth/google";
import { LogIn, LogOut, User } from "lucide-react";

interface AuthButtonProps {
  onLogin: (token: string, email?: string) => void;
  onLogout: () => void;
  isAuthenticated: boolean;
  userEmail?: string;
}

export default function AuthButton({
  onLogin,
  onLogout,
  isAuthenticated,
  userEmail,
}: AuthButtonProps) {
  const [loading, setLoading] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  /**
   * implicit flow: browser receives access_token directly in the popup
   * postMessage — no server-side code exchange required.
   * scope: drive.file — strictly limited to files created by this app.
   */
  const login = useGoogleLogin({
    flow: "implicit",
    scope: "https://www.googleapis.com/auth/drive.file",
    onSuccess: async (tokenResponse) => {
      const token = tokenResponse.access_token;
      let email: string | undefined;
      try {
        const resp = await fetch(
          "https://www.googleapis.com/oauth2/v3/userinfo",
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (resp.ok) {
          const info = (await resp.json()) as { email?: string };
          email = info.email;
        }
      } catch {
        /* userinfo is not critical */
      }
      setLoading(false);
      setLoginError(null);
      onLogin(token, email);
    },
    onError: (err) => {
      setLoading(false);
      setLoginError(
        String(err.error_description ?? err.error ?? "Login failed")
      );
    },
  });

  if (isAuthenticated) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 bg-emerald-900/40 border border-emerald-700/50 rounded-full px-4 py-2">
          <User className="w-4 h-4 text-emerald-400" />
          <span className="text-sm text-emerald-300 font-medium">
            {userEmail ?? "Drive connected"}
          </span>
        </div>
        <button
          onClick={() => {
            googleLogout();
            onLogout();
          }}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        onClick={() => {
          setLoading(true);
          setLoginError(null);
          login();
        }}
        disabled={loading}
        className="flex items-center gap-3 bg-white hover:bg-slate-100 disabled:bg-slate-300 text-slate-800 font-semibold px-6 py-3 rounded-xl shadow-lg transition-colors"
      >
        {/* Google G colour SVG */}
        <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24">
          <path
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            fill="#4285F4"
          />
          <path
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            fill="#34A853"
          />
          <path
            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            fill="#FBBC05"
          />
          <path
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            fill="#EA4335"
          />
        </svg>
        <LogIn className="w-4 h-4" />
        {loading ? "Connecting…" : "Sign in with Google"}
      </button>
      {loginError && (
        <p className="text-red-400 text-xs">{loginError}</p>
      )}
    </div>
  );
}
