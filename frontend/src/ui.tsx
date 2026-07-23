import { useEffect, useState, type ReactNode } from "react";

/** ¿Estamos en pantalla estrecha? Para lo que CSS no puede resolver solo
 *  (props de recharts, cambiar tabla por tarjetas). Presentación, nada más. */
export function useEsMovil(ancho = 768) {
  const [esMovil, setEsMovil] = useState(
    () => typeof window !== "undefined" && window.innerWidth < ancho,
  );
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${ancho - 1}px)`);
    const alCambiar = () => setEsMovil(mq.matches);
    alCambiar();
    mq.addEventListener("change", alCambiar);
    return () => mq.removeEventListener("change", alCambiar);
  }, [ancho]);
  return esMovil;
}

/* Primitivas de UI del terminal. Sobrias por diseño: escala de grises + un acento
   frío + estados semánticos de baja saturación. Sin sombras llamativas ni adornos. */

export function Card({
  titulo,
  children,
  acciones,
  subtitulo,
  className = "",
}: {
  titulo?: string;
  children: ReactNode;
  acciones?: ReactNode;
  subtitulo?: string;
  className?: string;
}) {
  return (
    <section className={`bg-surface border border-line rounded-lg ${className}`}>
      {(titulo || acciones) && (
        <header className="flex items-center justify-between gap-3 px-3 md:px-4 min-h-[44px] md:h-11 py-2 md:py-0 border-b border-line">
          <div className="min-w-0">
            {titulo && (
              <h2 className="text-sm md:text-[13px] font-semibold text-fg tracking-tight truncate">{titulo}</h2>
            )}
            {subtitulo && <p className="text-[11px] text-faint truncate">{subtitulo}</p>}
          </div>
          {acciones && <div className="flex items-center gap-2 shrink-0">{acciones}</div>}
        </header>
      )}
      <div className="p-3 md:p-4">{children}</div>
    </section>
  );
}

export function Boton({
  children,
  onClick,
  variante = "primario",
  tipo = "button",
  disabled,
  title,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  variante?: "primario" | "secundario" | "fantasma" | "peligro";
  tipo?: "button" | "submit";
  disabled?: boolean;
  title?: string;
  className?: string;
}) {
  const estilos = {
    primario: "bg-accent text-accent-contrast hover:bg-accent/90",
    secundario: "bg-elevated text-fg border border-line hover:border-muted/40",
    fantasma: "text-muted hover:text-fg hover:bg-elevated",
    peligro: "bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20",
  }[variante];
  return (
    <button
      type={tipo}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex items-center justify-center gap-1.5 px-4 md:px-3 min-h-[44px] md:min-h-0 md:py-1.5 rounded-md text-sm md:text-[13px] font-medium transition disabled:opacity-40 disabled:cursor-not-allowed ${estilos} ${className}`}
    >
      {children}
    </button>
  );
}

/** Estado de calidad del dato: punto de color + etiqueta discreta.
 *  Nunca se muestra un score sin su calidad (§11). */
export function BadgeCalidad({ estado }: { estado?: string | null }) {
  if (!estado) return <span className="text-faint">—</span>;
  const punto =
    {
      COMPLETO: "bg-positive",
      PARCIAL: "bg-warning",
      NO_CALCULABLE: "bg-faint",
      DESCARTADO_RIESGO: "bg-danger",
    }[estado] || "bg-faint";
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted whitespace-nowrap">
      <span className={`h-1.5 w-1.5 rounded-full ${punto}`} />
      {estado}
    </span>
  );
}

/** Tramo del score. El color comunica (no es semáforo): alto = positivo sobrio,
 *  medio = neutro con barra de acento, bajo = atenuado. */
export function tramoScore(valor: number) {
  if (valor >= 70) return { texto: "text-positive", fondo: "bg-positive", nivel: "alto" };
  if (valor >= 45) return { texto: "text-fg", fondo: "bg-accent", nivel: "medio" };
  return { texto: "text-muted", fondo: "bg-faint", nivel: "bajo" };
}

/** Score como cifra central: número monoespaciado + micro-medidor por tramo. */
export function ScoreCelda({ valor }: { valor: number | string | null | undefined }) {
  if (valor === null || valor === undefined)
    return <span className="cifra text-sm text-faint">—</span>;
  const n = Number(valor);
  const t = tramoScore(n);
  return (
    <div className="flex items-center gap-2.5 justify-end">
      <span className="h-1 w-9 rounded-full bg-line overflow-hidden">
        <span className={`block h-full rounded-full ${t.fondo}`} style={{ width: `${Math.max(4, Math.min(100, n))}%` }} />
      </span>
      <span className={`cifra text-[15px] font-semibold ${t.texto}`}>{n.toFixed(1)}</span>
    </div>
  );
}

/** Score compacto (sin medidor) para contextos secundarios. */
export function BadgeScore({ valor }: { valor: number | string | null | undefined }) {
  if (valor === null || valor === undefined)
    return <span className="cifra text-sm text-faint">—</span>;
  const n = Number(valor);
  return <span className={`cifra text-sm font-semibold ${tramoScore(n).texto}`}>{n.toFixed(1)}</span>;
}

/** Discreto a propósito: en un ranking casi todo es provisional al arrancar, así que
 *  un badge saturado por fila taparía al score, que es lo que manda en la pantalla. */
export function AvisoProvisional() {
  return (
    <span
      title="Calculado con parámetros provisionales (sin fuente validada)"
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-warning/70 border border-warning/20"
    >
      PROV
    </span>
  );
}

export function BadgeDup() {
  return (
    <span
      title="Posible duplicado en otro portal"
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted border border-line"
    >
      DUP
    </span>
  );
}

/** Zona turística: distingue de un vistazo (sin entrar a la ficha) un inmueble cuyo
 *  score de cashflow no es representativo (plusvalía / corta estancia). */
export function BadgeTuristica() {
  return (
    <span
      title="Zona turística: el score de cashflow (larga estancia, apalancado) no es representativo aquí. La inversión es de plusvalía / alquiler de corta estancia."
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent border border-accent/40"
    >
      TURÍSTICA
    </span>
  );
}

/** Etiqueta genérica (señales, códigos, estados). */
export function Chip({
  children,
  tono = "neutro",
  title,
}: {
  children: ReactNode;
  tono?: "neutro" | "danger" | "warning" | "positive" | "accent";
  title?: string;
}) {
  const tonos = {
    neutro: "text-muted border-line bg-elevated",
    danger: "text-danger border-danger/30 bg-danger/10",
    warning: "text-warning border-warning/30 bg-warning/10",
    positive: "text-positive border-positive/30 bg-positive/10",
    accent: "text-accent border-accent/30 bg-accent/10",
  }[tono];
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium border ${tonos}`}
    >
      {children}
    </span>
  );
}

/** Interruptor sobrio (toggle). */
export function Interruptor({
  activo,
  onCambiar,
  etiqueta,
  title,
}: {
  activo: boolean;
  onCambiar: (v: boolean) => void;
  etiqueta?: ReactNode;
  title?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      title={title}
      onClick={() => onCambiar(!activo)}
      className="inline-flex items-center gap-2.5 text-sm md:text-[13px] text-muted hover:text-fg transition select-none min-h-[44px] md:min-h-0 py-2 md:py-0"
    >
      <span className={`relative h-4 w-7 rounded-full transition-colors ${activo ? "bg-accent" : "bg-line"}`}>
        <span
          className={`absolute top-0.5 h-3 w-3 rounded-full bg-[hsl(210_40%_98%)] shadow-sm transition-all ${activo ? "left-3.5" : "left-0.5"}`}
        />
      </span>
      {etiqueta}
    </button>
  );
}

export function Vacio({ children }: { children: ReactNode }) {
  return <div className="text-sm text-faint py-8 text-center">{children}</div>;
}

export function IconoAviso({ className = "" }: { className?: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className={`shrink-0 ${className}`} aria-hidden>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

/** Aviso de consecuencia silenciosa: el sistema NO falla, pero calibra mal y hacia
 *  arriba. Va en tono danger a propósito — es lo que puede engañar al que decide. */
export function AvisoRiesgo({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-2 rounded-md border border-danger/40 bg-danger/10 px-2.5 py-2 text-xs text-danger leading-relaxed">
      <IconoAviso className="mt-0.5" />
      <span>{children}</span>
    </div>
  );
}

/** Marca de ranking: el score ignoró señales que el catálogo del país no contempla. */
export function BadgeSenalIgnorada({ pais }: { pais?: string | null }) {
  return (
    <span
      title={`El analista emitió señales que el catálogo de ${pais || "este país"} no contempla. No se aplicaron al score: ni descarte duro ni penalización. El score puede estar infra-penalizado.`}
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-danger border border-danger/40 bg-danger/10"
    >
      SEÑAL IGNORADA
    </span>
  );
}

/* --- Formato de cifras (todas en monoespaciada, alineadas a la derecha) --- */

export function fmtDinero(valor: unknown, moneda?: string | null) {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return "—";
  return `${n.toLocaleString("es-ES", { maximumFractionDigits: 0 })}${moneda ? " " + moneda : ""}`;
}

export function fmtNum(valor: unknown, decimales = 0) {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString("es-ES", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
}

/** Redondeo SOLO de presentación para las métricas del motor.
 *  El motor trabaja en Decimal exacto y así se guarda; volcar los 28 dígitos en
 *  pantalla no es precisión, es ruido. El valor exacto sigue en la auditoría (hover).
 *  Sin semántica de negocio: los ratios (|v|<1) llevan 4 decimales, el resto 2. */
export function fmtMetrica(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return String(valor);
  const abs = Math.abs(n);
  if (abs !== 0 && abs < 1) return n.toFixed(4);
  return n.toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
