import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Tema = "dark" | "light";

// Oscuro por defecto. Debe coincidir con el bootstrap de index.html, que aplica el
// tema antes del primer pintado; si divergen, se vería un parpadeo al arrancar.
const TEMA_POR_DEFECTO: Tema = "dark";

const Ctx = createContext<{ tema: Tema; alternar: () => void }>({
  tema: "dark",
  alternar: () => {},
});

export function ProveedorTema({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema>(
    () => (localStorage.getItem("tema") as Tema) || TEMA_POR_DEFECTO,
  );

  useEffect(() => {
    const raiz = document.documentElement;
    raiz.classList.toggle("dark", tema === "dark");
    raiz.style.colorScheme = tema;
    localStorage.setItem("tema", tema);
  }, [tema]);

  return (
    <Ctx.Provider value={{ tema, alternar: () => setTema((t) => (t === "dark" ? "light" : "dark")) }}>
      {children}
    </Ctx.Provider>
  );
}

export const useTema = () => useContext(Ctx);

/** Paleta para recharts (necesita colores concretos, no variables CSS).
 *  Mismos valores que los tokens de index.css, por tema. */
export function coloresGrafico(tema: Tema) {
  return tema === "dark"
    ? {
        barra: "hsl(205 90% 60%)",
        barraTenue: "hsl(205 40% 30%)",
        linea: "hsl(205 90% 60%)",
        grid: "hsl(220 12% 19%)",
        eje: "hsl(215 12% 60%)",
        etiqueta: "hsl(210 17% 91%)",
        superficie: "hsl(220 15% 10%)",
        positivo: "hsl(162 52% 46%)",
        negativo: "hsl(4 66% 60%)",
      }
    : {
        barra: "hsl(211 90% 44%)",
        barraTenue: "hsl(211 70% 82%)",
        linea: "hsl(211 90% 44%)",
        grid: "hsl(214 20% 89%)",
        eje: "hsl(215 16% 42%)",
        etiqueta: "hsl(217 28% 16%)",
        superficie: "hsl(0 0% 100%)",
        positivo: "hsl(162 62% 32%)",
        negativo: "hsl(4 68% 46%)",
      };
}
