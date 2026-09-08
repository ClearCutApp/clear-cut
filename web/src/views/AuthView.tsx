import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { createUserWithEmailAndPassword, getRedirectResult, GoogleAuthProvider,
  sendEmailVerification, sendPasswordResetEmail, signInWithEmailAndPassword,
  signInWithPopup, signInWithRedirect, type UserCredential } from "firebase/auth";
import { firebaseAuth } from "../auth/firebase";
import { GoogleMark } from "../components/atoms/GoogleMark";
import { useAuth } from "../state/AuthContext";
import { LanguageSwitch, useLocale } from "../state/LocaleContext";

export function safeDestination(value: unknown): string {
  return typeof value === "string" && /^\/(?:projects(?:\/|$)|team(?:$|[#?])|join(?:$|[#?]))/.test(value) && !value.includes("\\")
    ? value : "/projects";
}

/** Firebase reports failures as a `code`; anything else is an unknown failure. */
export function authErrorCode(error: unknown): string {
  return typeof error === "object" && error !== null && "code" in error
    && typeof (error as { code: unknown }).code === "string" ? (error as { code: string }).code : "";
}

/** Closing the chooser is a decision, not a failure, and must not be reported
 *  as one. `cancelled-popup-request` fires when a second popup supersedes the
 *  first, which is the same decision arriving twice. */
const CANCELLED = new Set(["auth/popup-closed-by-user", "auth/cancelled-popup-request",
  "auth/user-cancelled"]);

/** The environment refused the popup rather than the sign-in. A redirect asks
 *  the same question without one, so it is a fallback and not a second error. */
const NEEDS_REDIRECT = new Set(["auth/popup-blocked",
  "auth/operation-not-supported-in-this-environment", "auth/web-storage-unsupported"]);
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

  async function settle(result: UserCredential) {
    if (!result.user.emailVerified) {
      if (signup) await sendEmailVerification(result.user);
      await navigate("/verify-email", { replace: true, state: { from: destination } });
    } else await navigate(destination, { replace: true });
  }

  /* A redirect leaves the page, so the credential arrives on the way back and
     has to be collected here rather than where the button was pressed. */
  useEffect(() => {
    const auth = firebaseAuth();
    if (!auth) return;
    let active = true;
    void getRedirectResult(auth).then((result) => {
      if (active && result) void settle(result);
    }).catch(() => {
      if (active) setMessage(text("We could not complete that sign-in. Please try again.",
        "No se pudo completar el ingreso. Volvé a intentarlo."));
    });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function signInWithGoogle(auth: ReturnType<typeof firebaseAuth> & object) {
    try {
      await settle(await signInWithPopup(auth, new GoogleAuthProvider()));
    } catch (error) {
      const code = authErrorCode(error);
      if (CANCELLED.has(code)) return;
      if (NEEDS_REDIRECT.has(code)) { await signInWithRedirect(auth, new GoogleAuthProvider()); return; }
      if (code === "auth/unauthorized-domain") {
        setMessage(text("This address is not an authorised sign-in domain for this workspace.",
          "Esta dirección no es un dominio de ingreso autorizado para este espacio."));
        return;
      }
      if (code === "auth/account-exists-with-different-credential") {
        setMessage(text("That email already signs in another way. Use your password instead.",
          "Ese correo ya ingresa de otra forma. Usá tu contraseña."));
        return;
      }
      throw error;
    }
  }

  async function perform(kind: "email" | "google" | "reset") {
    const auth = firebaseAuth();
    if (!auth) { setMessage(text("Account access is awaiting configuration.", "El acceso a cuentas está pendiente de configuración.")); return; }
    setBusy(true);
      setMessage(null);
    try {
      if (kind === "reset") {
        await sendPasswordResetEmail(auth, email);
        setMessage(text("If an account exists, a reset link will arrive by email.", "Si la cuenta existe, recibirás un enlace para restablecer la contraseña."));
      } else if (kind === "google") {
        await signInWithGoogle(auth);
      } else {
        await settle(signup ? await createUserWithEmailAndPassword(auth, email, password)
          : await signInWithEmailAndPassword(auth, email, password));
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
      {identity.ready && !identity.configured && <p className="auth-notice" id="auth-unconfigured" role="alert">{text("Account access is awaiting configuration.", "El acceso a cuentas está pendiente de configuración.")}</p>}
      <button type="button" className="auth-google" disabled={busy || !identity.configured}
        aria-describedby={identity.configured ? undefined : "auth-unconfigured"}
        onClick={() => void perform("google")}>
        <GoogleMark />
        {text("Continue with Google", "Continuar con Google")}
      </button>
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
