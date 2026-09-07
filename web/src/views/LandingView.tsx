import { Link } from "react-router";
import { ArrowRight, Play } from "lucide-react";
import { LanguageSwitch, useLocale } from "../state/LocaleContext";

export function LandingView() {
  const { text } = useLocale();
  return <main className="landing">
    <section className="landing-hero">
      <img className="landing-hero__image" src="/clearcut-film-set.png" alt="" fetchPriority="high" />
      <nav className="landing-nav" aria-label={text("Main", "Principal")}>
        <Link className="landing-nav__brand" to="/">ClearCut<span>.</span>
      </Link>
        <div>
      <LanguageSwitch />
      <Link to="/login">{text("Sign in", "Ingresar")}</Link>
          <Link className="landing-button" to="/signup">{text("Get started", "Comenzar")}<ArrowRight size={16} />
      </Link>
      </div>
      </nav>
      <div className="landing-hero__copy">
        <p className="landing-eyebrow">{text("FROM THE FIRST DRAFT TO THE FINAL FRAME", "DEL PRIMER GUION AL ÚLTIMO PLANO")}</p>
        <h1>ClearCut<span>.</span>
      </h1>
        <h2>{text("Keep the story.", "Conserva la historia.")}<br />{text("Clear the way.", "Despeja el camino.")}</h2>
        <p className="landing-intro">{text("A shared workspace to examine the rights behind your screenplay, scene by scene.", "Un espacio de trabajo para examinar los derechos de tu guion, escena por escena.")}</p>
        <Link className="landing-button landing-button--large" to="/signup">{text("Start your workspace", "Crear tu espacio")}<ArrowRight size={18} />
      </Link>
        <a className="landing-watch" href="#workflow">
      <Play size={14} />{text("Explore the workflow", "Conocer el proceso")}</a>
      </div>
      <p className="landing-hero__caption">{text("LESS UNCERTAINTY. MORE ROOM TO CREATE.", "MENOS INCERTIDUMBRE. MÁS ESPACIO PARA CREAR.")}</p>
    </section>
    <section id="workflow" className="landing-workflow">
      <div>
      <p className="landing-eyebrow">{text("THE WORK BETWEEN THE LINES", "EL TRABAJO ENTRE LÍNEAS")}</p>
        <h2>{text("Every scene has a story.", "Cada escena tiene una historia.")}<br />
      <em>{text("And a few questions.", "Y algunas preguntas.")}</em>
      </h2>
        <p>{text("Bring your screenplay into focus. Review potential rights issues with cited research, then record the decisions your production makes.", "Pon tu guion en foco. Revisa posibles cuestiones de derechos con fuentes citadas y registra las decisiones de tu producción.")}</p>
        <ol>
      <li>
      <span>01</span>{text("Bring in the screenplay", "Carga el guion")}</li>
      <li>
      <span>02</span>{text("Examine scenes and sources", "Revisa escenas y fuentes")}</li>
      <li>
      <span>03</span>{text("Track human clearance decisions", "Registra decisiones de autorización")}</li>
      </ol>
      </div>
      <div className="landing-script" aria-label={text("Illustrative screenplay excerpt", "Fragmento ilustrativo de guion")}>
        <header>{text("THE LAST LIGHT", "LA ÚLTIMA LUZ")} <span>{text("ILLUSTRATIVE EXCERPT", "EJEMPLO ILUSTRATIVO")}</span>
      </header>
        <p>{text("INT. RECORD STORE — NIGHT", "INT. TIENDA DE DISCOS — NOCHE")}</p>
      <p>{text("Rain traces the window. MARA turns a record over in her hands.", "La lluvia recorre la ventana. MARA gira un disco entre sus manos.")}</p>
        <p className="landing-script__character">MARA</p>
      <p className="landing-script__dialogue">{text("Some songs bring you right back.", "Algunas canciones te llevan de vuelta.")}</p>
        <p>{text("A familiar ", "Una conocida ")}<mark>{text("song plays on the radio.", "canción suena en la radio.")}</mark>
      </p>
        <aside>
      <strong>{text("Music rights", "Derechos musicales")}</strong>
      <p>{text("Identify the composition and recording. Review permission requirements before filming.", "Identifica la composición y la grabación. Revisa los permisos antes de filmar.")}</p>
      <small>{text("Research supports a decision. Your team confirms clearance.", "La investigación apoya la decisión. Tu equipo confirma la autorización.")}</small>
      </aside>
      </div>
    </section>
    <section className="landing-close">
      <p className="landing-eyebrow">{text("MAKE ROOM FOR THE NEXT DRAFT", "ESPACIO PARA EL PRÓXIMO GUION")}</p>
      <h2>{text("Your story starts here.", "Tu historia comienza aquí.")}</h2>
      <Link className="landing-button landing-button--large" to="/signup">{text("Create an account", "Crear una cuenta")}<ArrowRight size={18} />
      </Link>
      </section>
    <footer className="landing-footer">
      <Link to="/">ClearCut.</Link>
      <span>{text("For the people behind the picture.", "Para quienes hacen posible la película.")}</span>
      <LanguageSwitch />
      </footer>
  </main>;
}
