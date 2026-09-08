import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { createUserWithEmailAndPassword, GoogleAuthProvider, sendEmailVerification,
  sendPasswordResetEmail, signInWithEmailAndPassword, signInWithPopup } from "firebase/auth";
import { firebaseAuth } from "../auth/firebase";
import { useAuth } from "../state/AuthContext";
import { LanguageSwitch, useLocale } from "../state/LocaleContext";

export function safeDestination(value: unknown): string {
  return typeof value === "string" && /^\/(?:projects(?:\/|$)|team(?:$|[#?])|join(?:$|[#?]))/.test(value) && !value.includes("\\")
    ? value : "/projects";
}
export function AuthView({ signup = false }: { signup?: boolean }) {
  const { text } = useLocale();
  const identity = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const destination = safeDestination((location.state as { from?: unknown } | null)?.from);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  if (identity.user?.emailVerified) return <Navigate to={destination} replace />;

  async function perform(kind: "email" | "google" | "reset") {
    const auth = firebaseAuth();
    if (!auth) { setMessage(text("Account access is awaiting configuration.", "El acceso a cuentas está pendiente de configuración.")); return; }
    setBusy(true);
      setMessage(null);
    try {
      if (kind === "reset") {
        await sendPasswordResetEmail(auth, email);
        setMessage(text("If an account exists, a reset link will arrive by email.", "Si la cuenta existe, recibirás un enlace para restablecer la contraseña."));
      } else {
        const result = kind === "google" ? await signInWithPopup(auth, new GoogleAuthProvider())
          : signup ? await createUserWithEmailAndPassword(auth, email, password)
          : await signInWithEmailAndPassword(auth, email, password);
        if (!result.user.emailVerified) {
          if (signup) await sendEmailVerification(result.user);
          await navigate("/verify-email", { replace: true, state: { from: destination } });
        } else await navigate(destination, { replace: true });
      }
    } catch {
      setMessage(text("We could not complete that request. Check your details or try again.", "No se pudo completar la solicitud. Revisa los datos o vuelve a intentarlo."));
    } finally { setBusy(false); }
  }
  function submit(event: FormEvent) { event.preventDefault();
      void perform("email"); }
  return <main className="auth-page">
      <nav>
      <Link className="auth-brand" to="/">ClearCut.</Link>
      <LanguageSwitch />
      </nav>
    <section className="auth-content">
      <p className="landing-eyebrow">{text("YOUR NEXT PRODUCTION", "TU PRÓXIMA PRODUCCIÓN")}</p>
      <h1>{signup ? text("Make space for your story.", "Crea espacio para tu historia.") : text("Welcome back.", "Te damos la bienvenida.")}</h1>
      <p>{text("Your scripts, research and production decisions, together.", "Tus guiones, investigación y decisiones de producción, en un solo lugar.")}</p>
      {identity.ready && !identity.configured && <p role="alert">{text("Account access is awaiting configuration.", "El acceso a cuentas está pendiente de configuración.")}</p>}
      <button type="button" className="auth-google" disabled={busy || !identity.configured} onClick={() => void perform("google")}>{text("Continue with Google", "Continuar con Google")}</button>
      <div className="auth-divider">{text("or use email", "o usa tu correo")}</div>
      <form onSubmit={submit}>
        <label>{text("Email", "Correo electrónico")}<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} />
      </label>
        <label>{text("Password", "Contraseña")}<input required type="password" minLength={8} autoComplete={signup ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} />
      </label>
        <button className="landing-button" disabled={busy || !identity.configured}>{busy ? text("Please wait…", "Espera…") : signup ? text("Create account", "Crear cuenta") : text("Sign in", "Ingresar")}</button>
      </form>
      {message && <p role="status">{message}</p>}
      {!signup && <button className="auth-link" disabled={busy || !email || !identity.configured} onClick={() => void perform("reset")}>{text("Reset password", "Restablecer contraseña")}</button>}
      <p>{signup ? text("Already have an account?", "¿Ya tienes una cuenta?") : text("New to ClearCut?", "¿Es tu primera vez?")} <Link to={signup ? "/login" : "/signup"} state={{ from: destination }}>{signup ? text("Sign in", "Ingresar") : text("Create account", "Crear cuenta")}</Link>
      </p>
    </section>
      <div className="auth-image" aria-hidden="true" />
      </main>;
}
