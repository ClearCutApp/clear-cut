import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { safeDestination } from "./AuthView";
import { sendEmailVerification } from "firebase/auth";
import { logOut, useAuth } from "../state/AuthContext";
import { useLocale } from "../state/LocaleContext";

export function VerifyEmailView() {
  const { user, ready } = useAuth();
  const { text } = useLocale();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const destination = safeDestination((location.state as { from?: unknown } | null)?.from);
  if (ready && !user) return <Navigate to="/login" replace />;
  async function verify(resend: boolean) {
    if (!user) return;
    setBusy(true);
    try {
      if (resend) { await sendEmailVerification(user);
      setMessage(text("Verification email sent.", "Correo de verificación enviado.")); }
      else { await user.reload(); await user.getIdToken(true);
        if (user.emailVerified) { await navigate(destination, { replace: true }); }
        else setMessage(text("Open the link in your email, then check again.", "Abre el enlace del correo y vuelve a comprobarlo.")); }
    } catch { setMessage(text("Could not verify your email. Try again.", "No se pudo verificar el correo. Inténtalo de nuevo.")); }
    finally { setBusy(false); }
  }
  return <main className="auth-page">
      <section className="auth-content">
      <Link className="auth-brand" to="/">ClearCut.</Link>
    <h1>{text("Check your inbox.", "Revisa tu correo.")}</h1>
      <p>{text("Verify your email before opening a private workspace.", "Verifica tu correo antes de abrir un espacio privado.")}</p>
    <p>{user?.email}</p>
      <button className="landing-button" disabled={busy} onClick={() => void verify(false)}>{text("I verified my email", "Ya verifiqué mi correo")}</button>
    <button className="auth-link" disabled={busy} onClick={() => void verify(true)}>{text("Send another email", "Enviar otro correo")}</button>
    <button className="auth-link" onClick={() => void logOut()}>{text("Sign out", "Cerrar sesión")}</button>
    {message && <p role="status">{message}</p>}</section>
      </main>;
}
