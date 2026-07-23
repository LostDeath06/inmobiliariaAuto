import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
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
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [desplazado, setDesplazado] = useState(false);
  const { pathname } = useLocation();

  // Al navegar, cerrar el menú: en móvil se queda abierto tapando la pantalla.
  useEffect(() => { setMenuAbierto(false); }, [pathname]);

  // La cabecera solo proyecta sombra cuando hay contenido pasando por debajo.
  // En el tope de la página no hay nada que separar, y una sombra ahí es ruido.
  useEffect(() => {
    const alDesplazar = () => setDesplazado(window.scrollY > 4);
    alDesplazar();
    window.addEventListener("scroll", alDesplazar, { passive: true });
    return () => window.removeEventListener("scroll", alDesplazar);
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-base">
      <header
        className={`sticky top-0 z-20 bg-surface/95 backdrop-blur border-b transition-[box-shadow,border-color] duration-200 ${
          desplazado ? "shadow-elev-2 border-line" : "border-line/60"
        }`}
      >
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 h-14 flex items-center gap-4 md:gap-8">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="h-5 w-5 rounded bg-accent shrink-0" aria-hidden />
            <span className="font-semibold tracking-tight text-fg text-[15px] whitespace-nowrap">
              Sourcing Inmobiliario
            </span>
          </div>

          {/* Navegación de escritorio. La pestaña activa lleva además una guía de
              acento debajo: el fondo solo no basta para saber dónde estás. */}
          <nav className="hidden lg:flex gap-0.5 text-[13px]">
            {enlaces.map((e) => (
              <NavLink
                key={e.a}
                to={e.a}
                end={e.a === "/"}
                className={({ isActive }) =>
                  `relative px-3 py-1.5 rounded-md whitespace-nowrap transition-colors duration-150 ${
                    isActive
                      ? "bg-elevated text-fg font-medium"
                      : "text-muted hover:text-fg hover:bg-elevated/60"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {e.t}
                    <span
                      className={`absolute left-3 right-3 -bottom-[7px] h-px bg-accent transition-opacity duration-200 ${
                        isActive ? "opacity-100" : "opacity-0"
                      }`}
                      aria-hidden
                    />
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1">
            <BotonTema />
            {/* Hamburguesa: solo en móvil */}
            <button
              onClick={() => setMenuAbierto((v) => !v)}
              aria-label="Menú"
              aria-expanded={menuAbierto}
              className="lg:hidden h-11 w-11 inline-flex items-center justify-center rounded-md text-muted hover:text-fg hover:bg-elevated transition"
            >
              {menuAbierto ? (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M3 6h18M3 12h18M3 18h18" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Panel desplegable de navegación (móvil). Cada entrada con 44px de alto. */}
        {menuAbierto && (
          <nav className="lg:hidden border-t border-line bg-surface px-2 py-2 space-y-0.5 desplegar shadow-elev-2">
            {enlaces.map((e) => (
              <NavLink
                key={e.a}
                to={e.a}
                end={e.a === "/"}
                className={({ isActive }) =>
                  `flex items-center min-h-[44px] px-3 rounded-md text-[15px] transition ${
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
        )}
      </header>

      <main className="flex-1 max-w-[1400px] w-full mx-auto px-4 md:px-6 py-4 md:py-6">
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
      className="h-11 w-11 md:h-8 md:w-8 inline-flex items-center justify-center rounded-md text-muted hover:text-fg hover:bg-elevated transition"
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
