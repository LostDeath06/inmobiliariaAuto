/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "system-ui",
          "sans-serif",
        ],
        // Todas las cifras (precios, ROI, scores) van en monoespaciada.
        mono: [
          "JetBrains Mono",
          "SFMono-Regular",
          "SF Mono",
          "Cascadia Code",
          "Consolas",
          "ui-monospace",
          "monospace",
        ],
      },
      // Los colores son variables CSS (ver index.css): un cambio de tema los reescribe.
      // Escala de grises por niveles + un único acento frío + estados semánticos sobrios.
      colors: {
        base: "hsl(var(--base) / <alpha-value>)",
        surface: "hsl(var(--surface) / <alpha-value>)",
        elevated: "hsl(var(--elevated) / <alpha-value>)",
        line: "hsl(var(--line) / <alpha-value>)",
        fg: "hsl(var(--fg) / <alpha-value>)",
        muted: "hsl(var(--muted) / <alpha-value>)",
        faint: "hsl(var(--faint) / <alpha-value>)",
        accent: "hsl(var(--accent) / <alpha-value>)",
        "accent-contrast": "hsl(var(--accent-contrast) / <alpha-value>)",
        positive: "hsl(var(--positive) / <alpha-value>)",
        warning: "hsl(var(--warning) / <alpha-value>)",
        danger: "hsl(var(--danger) / <alpha-value>)",
      },
      borderColor: {
        DEFAULT: "hsl(var(--line) / <alpha-value>)",
      },
      // Elevación por capas (ver index.css). Reposo → hover → flotante.
      boxShadow: {
        "elev-1": "var(--sombra-1)",
        "elev-2": "var(--sombra-2)",
        "elev-3": "var(--sombra-3)",
      },
      transitionDuration: {
        DEFAULT: "150ms",
      },
      // Todo sale con la misma curva: arranca rápido y frena. Nunca rebota.
      transitionTimingFunction: {
        DEFAULT: "cubic-bezier(0.2, 0, 0, 1)",
        sal: "cubic-bezier(0.2, 0, 0, 1)",
      },
    },
  },
  plugins: [],
};
