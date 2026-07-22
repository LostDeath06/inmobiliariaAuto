import { NavLink, Outlet } from "react-router-dom";
import { useTema } from "./tema";

const enlaces = [
  { a: "/", t: "Ranking" },
  { a: "/estado", t: "Estado por país" },
  { a: "/perfiles", t: "Perfiles" },
  { a: "/mercado", t: "Configuración" },
  { a: "/portales", t: "Portales" },
  { a: "/jobs", t: "Monitor" },
];

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-base">
      <header className="sticky top-0 z-20 bg-surface/90 backdrop-blur border-b border-line">
        <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center gap-8">
          <div className="flex items-center gap-2.5">
            <span className="h-5 w-5 rounded bg-accent" aria-hidden />
            <span className="font-semibold tracking-tight text-fg text-[15px]">
              Sourcing Inmobiliario
            </span>
          </div>
          <nav className="flex gap-0.5 text-[13px]">
            {enlaces.map((e) => (
              <NavLink
                key={e.a}
                to={e.a}
                end={e.a === "/"}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md transition ${
                    isActive
                      ? "bg-elevated text-fg font-medium"
                      : "text-muted hover:text-fg hover:bg-elevated/60"
                  }`
                }
              >
                {e.t}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto">
            <BotonTema />
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-[1400px] w-full mx-auto px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}

function BotonTema() {
  const { tema, alternar } = useTema();
  const oscuro = tema === "dark";
  return (
    <button
      onClick={alternar}
      title={oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
      aria-label="Cambiar tema"
      className="h-8 w-8 inline-flex items-center justify-center rounded-md text-muted hover:text-fg hover:bg-elevated transition"
    >
      {oscuro ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  );
}
