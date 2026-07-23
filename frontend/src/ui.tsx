import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

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

/** Índice para la aparición escalonada: `<li {...paso(i)}>` dentro de `.escalonado`. */
export const paso = (i: number) => ({ style: { "--i": i } as CSSProperties });

/* Primitivas de UI del terminal. Sobrias por diseño: escala de grises + un acento
   frío + estados semánticos de baja saturación. La profundidad viene de la
   elevación (sombras suaves + canto de 1px), nunca de brillos ni gradientes. */

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
    <section
      className={`bg-surface border border-line rounded-lg shadow-elev-1 transition-shadow duration-200 hover:shadow-elev-2 ${className}`}
    >
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
  cargando,
  title,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  variante?: "primario" | "secundario" | "fantasma" | "peligro";
  tipo?: "button" | "submit";
  disabled?: boolean;
  cargando?: boolean;
  title?: string;
  className?: string;
}) {
  const estilos = {
    primario: "bg-accent text-accent-contrast hover:bg-accent/90 shadow-elev-1 hover:shadow-elev-2",
    secundario: "bg-elevated text-fg border border-line hover:border-muted/40 shadow-elev-1 hover:shadow-elev-2",
    fantasma: "text-muted hover:text-fg hover:bg-elevated",
    peligro: "bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20",
  }[variante];
  return (
    <button
      type={tipo}
      onClick={onClick}
      disabled={disabled || cargando}
      title={title}
      className={`inline-flex items-center justify-center gap-1.5 px-3 py-1.5 tactil:px-4 tactil:py-0 tactil:min-h-[44px] rounded-md text-[13px] tactil:text-sm font-medium
        transition-[background-color,border-color,box-shadow,transform,opacity] duration-150
        active:translate-y-px disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none disabled:active:translate-y-0 ${estilos} ${className}`}
    >
      {cargando && <Girador />}
      {children}
    </button>
  );
}

/** Indicador de trabajo en curso. Funcional: dice que el sistema está ocupado. */
function Girador() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" className="shrink-0 animate-spin" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/* --- Pista: explicación consultable también con el dedo ---------------------
   Los `title` nativos no existen en táctil (§11.7): en un móvil los badges del
   ranking eran marcas mudas. Esta pista abre con pulsación y con hover, se
   posiciona en coordenadas de viewport (así no la recorta ningún contenedor con
   `overflow-hidden`) y se pega al borde si no cabe. -------------------------- */

export function Pista({
  children,
  texto,
  className = "",
}: {
  children: ReactNode;
  texto: string;
  className?: string;
}) {
  const [abierta, setAbierta] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const anclaRef = useRef<HTMLButtonElement>(null);
  const globoRef = useRef<HTMLDivElement>(null);

  const colocar = useCallback(() => {
    const ancla = anclaRef.current;
    const globo = globoRef.current;
    if (!ancla || !globo) return;
    const a = ancla.getBoundingClientRect();
    const g = globo.getBoundingClientRect();
    const margen = 8;
    const left = Math.min(
      Math.max(margen, a.left + a.width / 2 - g.width / 2),
      window.innerWidth - g.width - margen,
    );
    // Debajo por defecto; arriba si no cabe (móvil, badges al pie de la tarjeta).
    const cabeDebajo = a.bottom + g.height + margen < window.innerHeight;
    setPos({ top: cabeDebajo ? a.bottom + 6 : a.top - g.height - 6, left });
  }, []);

  useLayoutEffect(() => {
    if (abierta) colocar();
  }, [abierta, colocar]);

  useEffect(() => {
    if (!abierta) return;
    const cerrar = () => setAbierta(false);
    const alPulsarFuera = (e: PointerEvent) => {
      if (!anclaRef.current?.contains(e.target as Node)) cerrar();
    };
    const alTeclear = (e: KeyboardEvent) => e.key === "Escape" && cerrar();
    document.addEventListener("pointerdown", alPulsarFuera);
    document.addEventListener("keydown", alTeclear);
    window.addEventListener("scroll", cerrar, true);
    window.addEventListener("resize", cerrar);
    return () => {
      document.removeEventListener("pointerdown", alPulsarFuera);
      document.removeEventListener("keydown", alTeclear);
      window.removeEventListener("scroll", cerrar, true);
      window.removeEventListener("resize", cerrar);
    };
  }, [abierta]);

  return (
    <>
      <button
        ref={anclaRef}
        type="button"
        aria-label={texto}
        aria-expanded={abierta}
        onClick={(e) => {
          // En el ranking la tarjeta entera es un enlace: consultar la marca no
          // debe navegar a la ficha.
          e.preventDefault();
          e.stopPropagation();
          setAbierta((v) => !v);
        }}
        onMouseEnter={() => setAbierta(true)}
        onMouseLeave={() => setAbierta(false)}
        // El badge mide 18px de alto: se le amplía el área de pulsación con un
        // pseudo-elemento invisible (~42px) sin engordarlo ni descuadrar la fila.
        // Solo 2px a los lados, o dos marcas contiguas se solaparían.
        className={`relative inline-flex cursor-help before:absolute before:-inset-y-3 before:-inset-x-0.5 before:content-[''] ${className}`}
      >
        {children}
      </button>
      {abierta && (
        <div
          ref={globoRef}
          role="tooltip"
          style={{ top: pos?.top ?? -9999, left: pos?.left ?? -9999 }}
          className="fixed z-50 max-w-[min(20rem,calc(100vw-1rem))] rounded-md border border-line bg-surface
            px-2.5 py-2 text-xs leading-relaxed text-muted shadow-elev-3 aparecer pointer-events-none"
        >
          {texto}
        </div>
      )}
    </>
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

/** El medidor arranca vacío y se llena tras el primer pintado; después, cualquier
 *  cambio de valor (cambiar de perfil, quitar el riesgo país) recorre la barra en
 *  vez de saltar. Es lo único que se anima "despacio": comunica una magnitud. */
function useAnchoMedidor(valor: number) {
  const [ancho, setAncho] = useState(0);
  useEffect(() => {
    // `setTimeout` y no `requestAnimationFrame`: en una pestaña de fondo rAF no
    // dispara, y la barra se quedaría a cero hasta que el usuario la mirase.
    const t = setTimeout(() => setAncho(Math.max(3, Math.min(100, valor))), 16);
    return () => clearTimeout(t);
  }, [valor]);
  return ancho;
}

/** Score como cifra dominante de su fila: es lo que se viene a leer, así que pesa
 *  más que todo lo demás. `lg` en tarjeta móvil, `md` en la tabla, `sm` suelto. */
export function ScoreCelda({
  valor,
  tamano = "md",
}: {
  valor: number | string | null | undefined;
  tamano?: "sm" | "md" | "lg";
}) {
  const n = Number(valor);
  const vacio = valor === null || valor === undefined || Number.isNaN(n);
  const ancho = useAnchoMedidor(vacio ? 0 : n);
  if (vacio) return <span className="cifra text-sm text-faint">—</span>;
  const t = tramoScore(n);
  const dim = {
    sm: { num: "text-[15px]", barra: "w-9 h-1", hueco: "gap-2.5" },
    md: { num: "text-[19px]", barra: "w-12 h-1.5", hueco: "gap-3" },
    lg: { num: "text-[26px] leading-none", barra: "w-16 h-1.5", hueco: "gap-3" },
  }[tamano];
  return (
    <div className={`flex items-center justify-end ${dim.hueco}`}>
      <span className={`${dim.barra} rounded-full bg-line overflow-hidden shrink-0`}>
        <span
          className={`block h-full rounded-full ${t.fondo} transition-[width,background-color] duration-300 ease-sal`}
          style={{ width: `${ancho}%` }}
        />
      </span>
      <span className={`cifra ${dim.num} font-semibold tracking-tight ${t.texto}`}>{n.toFixed(1)}</span>
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

/* --- Marcas del ranking ------------------------------------------------------
   Tienen presencia (canto propio, mayúsculas, mono) pero ninguna compite con el
   score: sin relleno saturado y a 10px. Todas explican por qué están ahí. ---- */

const MARCA =
  "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide leading-none h-[18px] transition-colors duration-150";

/** Discreto a propósito: en un ranking casi todo es provisional al arrancar, así que
 *  un badge saturado por fila taparía al score, que es lo que manda en la pantalla. */
export function AvisoProvisional() {
  return (
    <Pista texto="Calculado con parámetros provisionales (sin fuente validada).">
      <span className={`${MARCA} text-warning/80 border border-warning/30 hover:bg-warning/10`}>PROV</span>
    </Pista>
  );
}

export function BadgeDup() {
  return (
    <Pista texto="Posible duplicado del mismo inmueble en otro portal (ciudad + precio ±5% + m² ±5%). Solo se marca, nunca se fusiona.">
      <span className={`${MARCA} text-muted border border-line hover:bg-elevated`}>DUP</span>
    </Pista>
  );
}

/** Zona turística: distingue de un vistazo (sin entrar a la ficha) un inmueble cuyo
 *  score de cashflow no es representativo (plusvalía / corta estancia). */
export function BadgeTuristica() {
  return (
    <Pista texto="Zona turística: el score de cashflow (larga estancia, apalancado) no es representativo aquí. La inversión es de plusvalía / alquiler de corta estancia.">
      <span className={`${MARCA} text-accent border border-accent/40 hover:bg-accent/10`}>TURÍSTICA</span>
    </Pista>
  );
}

/** CONFOTUR (Ley 158-01, RD): el inmueble no paga el impuesto de transferencia,
 *  así que su coste de adquisición es sensiblemente menor. Se marca en verde
 *  sobrio porque es una ventaja real sobre un inmueble idéntico sin ella. */
export function BadgeConfotur() {
  return (
    <Pista texto="Acogido a CONFOTUR (Ley 158-01): exento del impuesto de transferencia y del IPI durante 15 años. Su coste de adquisición es menor que el de un inmueble idéntico sin la exención, y el motor ya lo ha descontado.">
      <span className={`${MARCA} text-positive border border-positive/40 hover:bg-positive/10`}>
        CONFOTUR
      </span>
    </Pista>
  );
}

/** Marca de ranking: el score ignoró señales que el catálogo del país no contempla. */
export function BadgeSenalIgnorada({ pais }: { pais?: string | null }) {
  return (
    <Pista
      texto={`El analista emitió señales que el catálogo de ${pais || "este país"} no contempla. No se aplicaron al score: ni descarte duro ni penalización. El score puede estar infra-penalizado.`}
    >
      <span className={`${MARCA} text-danger border border-danger/40 bg-danger/10 hover:bg-danger/20`}>
        SEÑAL IGNORADA
      </span>
    </Pista>
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
      className="inline-flex items-center gap-2.5 text-[13px] tactil:text-sm text-muted hover:text-fg transition select-none py-0 tactil:min-h-[44px] tactil:py-2"
    >
      <span
        className={`relative h-4 w-7 rounded-full transition-colors duration-200 ${
          activo ? "bg-accent" : "bg-line"
        }`}
      >
        <span
          className={`absolute top-0.5 h-3 w-3 rounded-full bg-[hsl(210_40%_98%)] shadow-elev-1 transition-[left] duration-200 ease-sal ${
            activo ? "left-3.5" : "left-0.5"
          }`}
        />
      </span>
      {etiqueta}
    </button>
  );
}

/* --- Huecos y esperas -------------------------------------------------------- */

/** Un hueco no es un vacío: dice qué falta y qué hacer con ello.
 *
 *  Por defecto es UNA LÍNEA con su explicación al lado: un panel monumental por
 *  cada tabla vacía convertía la pantalla de configuración en scroll infinito.
 *  `variante="panel"` queda para el hueco protagonista de una pantalla (el
 *  ranking sin resultados), donde sí es lo único que hay que mirar. */
export function Vacio({
  children,
  titulo,
  accion,
  variante = "linea",
}: {
  children?: ReactNode;
  titulo?: string;
  accion?: ReactNode;
  variante?: "linea" | "panel";
}) {
  const icono = (
    <svg
      width={variante === "panel" ? 24 : 15}
      height={variante === "panel" ? 24 : 15}
      viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      className="text-faint shrink-0" aria-hidden
    >
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 9h18" />
      <path d="M8 14h8" strokeDasharray="2 3" />
    </svg>
  );

  if (variante === "panel") {
    return (
      <div className="aparecer flex flex-col items-center gap-2 py-8 px-4 text-center">
        {icono}
        {titulo && <p className="text-[13px] font-medium text-fg">{titulo}</p>}
        {children && <p className="text-[13px] text-muted max-w-md leading-relaxed">{children}</p>}
        {accion && <div className="mt-1">{accion}</div>}
      </div>
    );
  }
  return (
    <div className="aparecer flex items-start gap-2 py-2 text-[13px] leading-relaxed">
      <span className="mt-0.5">{icono}</span>
      <div className="min-w-0">
        {titulo && <span className="font-medium text-fg">{titulo}</span>}
        {titulo && children && <span className="text-muted"> — </span>}
        {children && <span className="text-muted">{children}</span>}
        {accion && <div className="mt-1.5">{accion}</div>}
      </div>
    </div>
  );
}

/** Bloque gris que insinúa la forma de lo que va a llegar. */
export function Esqueleto({ className = "" }: { className?: string }) {
  return <span className={`esqueleto block ${className}`} aria-hidden />;
}

/** Silueta del ranking: mismas alturas que la fila real, así no salta al llegar. */
export function EsqueletoRanking({ filas = 8 }: { filas?: number }) {
  return (
    <div aria-busy="true" aria-label="Cargando ranking">
      <div className="lg:hidden space-y-2">
        {Array.from({ length: filas }).map((_, i) => (
          <div key={i} className="rounded-lg border border-line bg-elevated/30 p-3 space-y-2.5">
            <div className="flex items-center justify-between">
              <Esqueleto className="h-3 w-6" />
              <Esqueleto className="h-6 w-24" />
            </div>
            <Esqueleto className="h-4 w-3/4" />
            <Esqueleto className="h-3 w-1/3" />
            <div className="flex justify-between pt-2 border-t border-line/70">
              <Esqueleto className="h-4 w-24" />
              <Esqueleto className="h-4 w-14" />
            </div>
          </div>
        ))}
      </div>
      <div className="hidden lg:block space-y-px">
        {Array.from({ length: filas }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 h-[41px] border-b border-line/70 px-3">
            <Esqueleto className="h-3 w-4" />
            <Esqueleto className="h-4 w-28" />
            <Esqueleto className="h-4 flex-1 max-w-sm" />
            <Esqueleto className="h-4 w-24" />
            <Esqueleto className="h-4 w-12" />
            <Esqueleto className="h-3 w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Silueta de la ficha: cabecera, tres tarjetas, dos gráficos. */
export function EsqueletoFicha() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Cargando ficha">
      <div className="space-y-2">
        <Esqueleto className="h-6 w-2/3 max-w-md" />
        <Esqueleto className="h-4 w-40" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="rounded-lg border border-line bg-surface shadow-elev-1 overflow-hidden">
            <div className="h-11 border-b border-line flex items-center px-4">
              <Esqueleto className="h-3.5 w-28" />
            </div>
            <div className="p-4 space-y-3">
              {[0, 1, 2, 3, 4].map((j) => (
                <div key={j} className="flex justify-between gap-6">
                  <Esqueleto className="h-3.5 w-24" />
                  <Esqueleto className="h-3.5 w-16" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[0, 1].map((i) => (
          <div key={i} className="rounded-lg border border-line bg-surface shadow-elev-1 overflow-hidden">
            <div className="h-11 border-b border-line flex items-center px-4">
              <Esqueleto className="h-3.5 w-36" />
            </div>
            <div className="p-4">
              <Esqueleto className="h-[190px] w-full" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* --- Avisos ------------------------------------------------------------------ */

/** Confirmación o error de una acción. Entra con un desplazamiento corto para que
 *  se note que ha ocurrido algo, y se va sola: no deja poso en la pantalla. */
export function Aviso({
  children,
  tono = "positive",
  alCerrar,
  msSalida = 6000,
}: {
  children: ReactNode;
  tono?: "positive" | "warning" | "danger";
  alCerrar?: () => void;
  msSalida?: number;
}) {
  useEffect(() => {
    if (!alCerrar || !msSalida) return;
    const t = setTimeout(alCerrar, msSalida);
    return () => clearTimeout(t);
  }, [alCerrar, msSalida, children]);
  const tonos = {
    positive: "text-positive bg-positive/10 border-positive/30",
    warning: "text-warning bg-warning/10 border-warning/30",
    danger: "text-danger bg-danger/10 border-danger/30",
  }[tono];
  return (
    <div role="status" className={`aparecer text-[13px] border rounded-md px-3 py-2 shadow-elev-1 ${tonos}`}>
      {children}
    </div>
  );
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

/* --- Formato de cifras (todas en monoespaciada, alineadas a la derecha) --- */

export function fmtDinero(valor: unknown, moneda?: string | null) {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return "—";
  return `${n.toLocaleString("es-ES", { maximumFractionDigits: 0 })}${moneda ? " " + moneda : ""}`;
}

/** Fecha y hora legibles. Un ISO crudo en una tabla no lo lee nadie. */
export function fmtFechaHora(valor: unknown): string {
  if (!valor) return "—";
  const d = new Date(String(valor));
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("es-ES", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

/** Duración entre dos instantes, en la unidad que toque. */
export function fmtDuracion(desde: unknown, hasta: unknown): string {
  if (!desde || !hasta) return "—";
  const a = new Date(String(desde)).getTime();
  const b = new Date(String(hasta)).getTime();
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return "—";
  const seg = Math.round((b - a) / 1000);
  if (seg < 60) return `${seg} s`;
  if (seg < 3600) return `${Math.floor(seg / 60)} min ${seg % 60} s`;
  return `${Math.floor(seg / 3600)} h ${Math.round((seg % 3600) / 60)} min`;
}

export function fmtNum(valor: unknown, decimales = 0) {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString("es-ES", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
}

/** Cantidad "limpia": hasta 2 decimales, sin ceros de cola. Para no volcar el
 *  `400.000000` crudo del Decimal de BD. 4300 → "4.300", 17.4 → "17,4". */
export function fmtCantidad(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return String(valor);
  return n.toLocaleString("es-ES", { maximumFractionDigits: 2 });
}

/** Fracción → porcentaje legible. El motor guarda 0.07; en pantalla es "7 %".
 *  Hasta 2 decimales sin ceros de cola: 0.0125 → "1,25 %", 0.10 → "10 %". */
export function fmtPorcentaje(fraccion: unknown): string {
  if (fraccion === null || fraccion === undefined || fraccion === "") return "—";
  const n = Number(fraccion);
  if (Number.isNaN(n)) return "—";
  return `${(n * 100).toLocaleString("es-ES", { maximumFractionDigits: 2 })} %`;
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
