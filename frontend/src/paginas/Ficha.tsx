import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { coloresGrafico, useTema } from "../tema";
import {
  Aviso, AvisoProvisional, BadgeCalidad, BadgeConfotur, BadgeScore, Boton, Card, Chip,
  EsqueletoFicha, IconoAviso, Vacio, fmtDinero, fmtMetrica, paso, useEsMovil,
} from "../ui";

export default function Ficha() {
  const { id } = useParams();
  const [datos, setDatos] = useState<any>(null);
  const [perfiles, setPerfiles] = useState<Record<string, string>>({});
  const [recalculando, setRecalculando] = useState(false);
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");

  const cargar = () => api.get(`/api/inmuebles/${id}`).then(setDatos).catch((e) => setError(String(e)));
  useEffect(() => { setDatos(null); cargar(); }, [id]);
  useEffect(() => {
    api.get("/api/perfiles").then((ps: any[]) =>
      setPerfiles(Object.fromEntries(ps.map((p) => [p.id, p.nombre]))),
    ).catch(() => {});
  }, []);

  const recalcular = async () => {
    setRecalculando(true);
    try {
      await api.post(`/api/inmuebles/${id}/recalcular`);
      await cargar();
      setAviso("Recalculado con la configuración de mercado actual.");
    } catch (e) {
      setError(String(e));
    } finally {
      setRecalculando(false);
    }
  };

  if (error) return <div className="aparecer text-sm text-danger bg-danger/10 border border-danger/30 rounded-md px-3 py-2 shadow-elev-1">{error}</div>;
  if (!datos) return <EsqueletoFicha />;

  const { inmueble, metricas, analisis, scores, historico_precios, zona } = datos;
  const noReconocidas: string[] = analisis?.senales_no_reconocidas || [];
  const zonaTuristica = zona?.perfil_zona === "TURISTICA";
  const faltantes: string[] = metricas?.campos_faltantes || [];
  const estadoAnalisis = datos.analisis_estado;

  const fijarConfotur = async (valor: boolean | null) => {
    setRecalculando(true);
    try {
      await api.put(`/api/inmuebles/${id}/confotur`, { tiene_confotur: valor });
      await cargar();
      setAviso(
        valor === null
          ? "CONFOTUR marcado como desconocido. El score vuelve a marcarse PARCIAL."
          : `CONFOTUR ${valor ? "confirmado" : "descartado"}. Métricas y scores recalculados.`,
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setRecalculando(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="aparecer flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
        <div className="min-w-0">
          <h1 className="text-base sm:text-lg font-semibold text-fg tracking-tight leading-snug">
            {inmueble.titulo || "(sin título)"}
          </h1>
          <p className="text-sm text-faint mt-0.5">
            {[...new Set([inmueble.barrio, inmueble.ciudad, inmueble.pais].filter(Boolean))].join(" · ") || "—"}
          </p>
        </div>
        {/* En móvil los dos botones ocupan la fila a partes iguales (área táctil amplia) */}
        <div className="flex gap-2 shrink-0">
          <a href={inmueble.url_anuncio} target="_blank" rel="noreferrer" className="flex-1 sm:flex-none">
            <Boton variante="secundario" className="w-full sm:w-auto">Ver anuncio</Boton>
          </a>
          <div className="flex-1 sm:flex-none">
            <Boton className="w-full sm:w-auto" cargando={recalculando} onClick={recalcular}>
              {recalculando ? "Recalculando" : "Recalcular"}
            </Boton>
          </div>
        </div>
      </div>

      {aviso && <Aviso alCerrar={() => setAviso("")}>{aviso}</Aviso>}

      {faltantes.length > 0 && <PanelFaltantes faltantes={faltantes} />}

      {estadoAnalisis?.analisis_fallido && (
        <div className="aparecer rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 shadow-elev-1">
          <div className="flex items-center gap-2 text-danger text-[13px] font-semibold uppercase tracking-wide">
            <IconoAviso /> El análisis cualitativo falló
          </div>
          <p className="text-[13px] text-muted mt-1 leading-relaxed">
            Sin análisis no hay nivel de reforma ni señales, así que el score se calcula con
            menos componentes de los que debería.
            {estadoAnalisis.motivo_fallo
              ? " Motivo registrado:"
              : " No se registró el motivo (análisis anterior a la versión que lo guarda)."}
          </p>
          {estadoAnalisis.motivo_fallo && (
            <pre className="mt-1.5 whitespace-pre-wrap break-words rounded bg-base/60 p-2 text-[11px] text-danger cifra">
              {estadoAnalisis.motivo_fallo}
            </pre>
          )}
        </div>
      )}

      {zonaTuristica && (
        <div className="aparecer rounded-lg border border-accent/40 bg-accent/10 px-4 py-3 shadow-elev-1">
          <div className="flex items-center gap-2 text-accent text-[13px] font-semibold uppercase tracking-wide">
            <IconoAviso /> Zona turística — el score de cashflow no es representativo aquí
          </div>
          <p className="text-[13px] text-muted mt-1 max-w-3xl leading-relaxed">
            Esta zona está marcada como <strong className="text-fg font-medium">turística</strong>: la inversión es de
            plusvalía y alquiler de <strong className="text-fg font-medium">corta estancia</strong>, no de cashflow de
            larga estancia apalancado. Un score bajo aquí no significa mala inversión, significa que el perfil no encaja.
            {zona?.tiene_datos_corta
              ? " Hay datos de corta estancia cargados para la zona."
              : " Aún faltan datos de corta estancia (ADR y ocupación) para analizarla en su perfil."}
          </p>
        </div>
      )}

      {noReconocidas.length > 0 && (
        <div className="aparecer rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 shadow-elev-1">
          <div className="flex items-center gap-2 text-danger text-[13px] font-semibold uppercase tracking-wide">
            <IconoAviso /> Señales fuera del catálogo de {inmueble.pais || "el país"}
          </div>
          <p className="text-[13px] text-muted mt-1 max-w-3xl leading-relaxed">
            El analista emitió códigos que el catálogo del país no contempla. No cruzaron con nada:
            ni descarte duro ni penalización. El score de abajo puede estar <strong className="text-fg font-medium">infra-penalizado</strong>,
            por eso no se marca como COMPLETO. O falta ese código en el catálogo del país, o el modelo lo alucinó.
          </p>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {noReconocidas.map((c) => <Chip key={c} tono="danger">{c}</Chip>)}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start escalonado">
        <div {...paso(0)}>
          <Card titulo="Datos">
            <dl className="text-sm divide-y divide-line/70">
              <Dato k="Precio" v={<span className="cifra text-fg">{fmtDinero(inmueble.precio, inmueble.moneda)}</span>} />
              <Dato k="Superficie útil" v={<span className="cifra">{inmueble.superficie_util_m2 ? `${inmueble.superficie_util_m2} m²` : "—"}</span>} />
              <Dato k="Superficie construida" v={<span className="cifra">{inmueble.superficie_construida_m2 ? `${inmueble.superficie_construida_m2} m²` : "—"}</span>} />
              <Dato k="Habitaciones" v={<span className="cifra">{inmueble.habitaciones ?? "—"}</span>} />
              <Dato k="Tipo anunciante" v={inmueble.tipo_anunciante || "—"} />
              <Dato k="Calidad del dato" v={<BadgeCalidad estado={inmueble.estado_calidad} />} />
            </dl>

            {/* El control aparece solo donde la exención existe: lo dispara el propio
                motor al marcar el dato como pendiente, no una lista de países en la UI. */}
            {(faltantes.includes("tiene_confotur[desconocido]") ||
              inmueble.tiene_confotur !== null) && (
              <ControlConfotur
                valor={inmueble.tiene_confotur}
                sugerencia={analisis?.menciona_exencion_fiscal}
                ocupado={recalculando}
                onCambiar={fijarConfotur}
              />
            )}

            {inmueble.posible_duplicado_cross_portal && (
              <p className="text-xs text-muted mt-3">Marcado como posible duplicado en otro portal.</p>
            )}
          </Card>
        </div>

        <div {...paso(1)}>
          <Card titulo="Score por perfil" subtitulo="cashflow vs. plusvalía">
            <div className="divide-y divide-line/70">
              {scores.map((s: any) => (
                <div key={s.perfil_id} className="py-2.5 first:pt-0 last:pb-0 space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[13px] text-fg truncate">
                      {perfiles[s.perfil_id] || String(s.perfil_id).slice(0, 8)}
                    </span>
                    {s.usa_parametros_provisionales && <AvisoProvisional />}
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <BadgeCalidad estado={s.estado_calidad} />
                    <div className="flex items-baseline gap-4">
                      <span className="text-[11px] uppercase tracking-wide text-faint">
                        bruto <BadgeScore valor={s.score_bruto} />
                      </span>
                      <span className="text-[11px] uppercase tracking-wide text-faint">
                        total <BadgeScore valor={s.score_total} />
                      </span>
                    </div>
                  </div>
                  {s.motivo_descarte?.length > 0 && (
                    <div className="text-xs text-danger">Descartado por: {s.motivo_descarte.join(", ")}</div>
                  )}
                </div>
              ))}
              {scores.length === 0 && (
                <Vacio titulo="Sin scores">
                  Este inmueble no se ha puntuado todavía. Pulsa «Recalcular» arriba.
                </Vacio>
              )}
            </div>
          </Card>
        </div>

        <div {...paso(2)}>
          <Card titulo="Análisis cualitativo" subtitulo="Claude · solo juicio, cero cifras">
            {analisis ? (
              <div className="space-y-3">
                <dl className="text-sm divide-y divide-line/70">
                  <Dato k="Estado" v={analisis.estado_conservacion} />
                  <Dato k="Reforma estimada" v={analisis.nivel_reforma_estimado} />
                  <Dato k="Tipología" v={analisis.tipologia} />
                  <Dato k="Apto alquiler larga" v={analisis.apto_alquiler_larga_estancia} />
                  <Dato k="Confianza" v={analisis.nivel_confianza} />
                </dl>
                <Senales titulo="Riesgos" codigos={analisis.senales_riesgo} tono="danger" />
                <Senales titulo="Oportunidades" codigos={analisis.senales_oportunidad} tono="positive" />
                {analisis.resumen_analista && (
                  <p className="text-[13px] text-muted leading-relaxed border-l-2 border-line pl-3">{analisis.resumen_analista}</p>
                )}
              </div>
            ) : (
              <Vacio titulo="Sin análisis">
                El análisis cualitativo está pendiente o falló. Recalcular vuelve a pedírselo a Claude.
              </Vacio>
            )}
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start escalonado">
        <div {...paso(3)}>
          <Card titulo="Desglose del score" subtitulo="contribución de cada componente">
            {scores[0]?.desglose?.componentes ? (
              <DesgloseChart desglose={scores[0].desglose} />
            ) : (
              <Vacio titulo="Sin desglose disponible">
                El desglose aparece cuando el motor puntúa el inmueble con una configuración de mercado cargada.
              </Vacio>
            )}
          </Card>
        </div>

        <div {...paso(4)}>
          <Card titulo="Histórico de precios" subtitulo="moneda nativa del anuncio">
            {historico_precios?.length >= 2 ? (
              <HistoricoChart puntos={historico_precios} moneda={inmueble.moneda} />
            ) : (
              <Vacio titulo="Un solo punto de precio">
                La serie aparece cuando el anuncio se vuelve a leer con otro precio. Aún no hay con qué comparar.
              </Vacio>
            )}
          </Card>
        </div>
      </div>

      <Card titulo="Métricas financieras" subtitulo="motor determinista · pulsa una cifra para ver su fórmula e inputs">
        {metricas ? (
          <PanelMetricas metricas={metricas} />
        ) : (
          <Vacio titulo="Sin métricas">
            El motor financiero no ha podido calcular nada: falta configuración de mercado del país.
          </Vacio>
        )}
      </Card>
    </div>
  );
}

/** CONFOTUR: lo decide el propietario, no Claude ni el sistema.
 *
 *  Tres estados de verdad, no dos: sí, no y *no lo sé*. «No lo sé» es el valor de
 *  partida y no equivale a «no lo tiene» — el motor lo distingue y degrada la
 *  calidad del dato mientras siga sin respuesta. */
function ControlConfotur({
  valor, sugerencia, ocupado, onCambiar,
}: {
  valor: boolean | null;
  sugerencia?: string | null;
  ocupado: boolean;
  onCambiar: (v: boolean | null) => void;
}) {
  const opciones: { etiqueta: string; v: boolean | null }[] = [
    { etiqueta: "Sí", v: true },
    { etiqueta: "No", v: false },
    { etiqueta: "No lo sé", v: null },
  ];
  return (
    <div className="mt-3 pt-3 border-t border-line/70">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wider text-faint">
          CONFOTUR (Ley 158-01)
        </span>
        {valor === true && <BadgeConfotur />}
      </div>

      <div className="inline-flex rounded-md border border-line overflow-hidden">
        {opciones.map((o) => {
          const activo = valor === o.v;
          return (
            <button
              key={String(o.v)}
              type="button"
              disabled={ocupado}
              onClick={() => onCambiar(o.v)}
              className={`px-2.5 py-1 tactil:py-2 tactil:min-h-[44px] text-[13px] transition-colors duration-150
                border-r border-line last:border-r-0 disabled:opacity-50 ${
                activo ? "bg-accent text-accent-contrast font-medium" : "text-muted hover:bg-elevated hover:text-fg"
              }`}
            >
              {o.etiqueta}
            </button>
          );
        })}
      </div>

      <p className="text-xs text-muted mt-1.5 leading-relaxed">
        {valor === true
          ? "Exento del impuesto de transferencia: el coste de adquisición ya lo descuenta."
          : valor === false
            ? "Paga el impuesto de transferencia como cualquier otro inmueble."
            : "Sin confirmar. El cálculo aplica el impuesto (hipótesis conservadora) y el score se queda en PARCIAL hasta que lo respondas."}
      </p>

      {sugerencia === "SI" && valor === null && (
        <p className="text-xs text-accent mt-1.5 leading-relaxed">
          El anuncio menciona CONFOTUR o una exención fiscal. Es una señal de lectura del
          texto, no una confirmación: verifícalo antes de marcarlo.
        </p>
      )}
    </div>
  );
}

/** Traduce `campos_faltantes` del motor a qué falta y dónde se carga.
 *
 *  El motor ya nombra internamente lo que le falta; lo que no había era manera de
 *  leerlo desde la ficha. Un inmueble NO_CALCULABLE dejaba de explicar por qué. */
function PanelFaltantes({ faltantes }: { faltantes: string[] }) {
  const explicar = (campo: string): { texto: string; ir?: string; enlace?: string } => {
    const dentro = campo.match(/\[(.+)\]/)?.[1] || "";
    if (campo.startsWith("coste_reforma"))
      return { texto: `Falta el coste de reforma (€/m²) para nivel ${dentro}`, ir: "/mercado", enlace: "Cargar costes de reforma" };
    if (campo === "gastos_adquisicion[sin_configurar]")
      return { texto: "No hay ningún gasto de adquisición configurado para el país", ir: "/mercado", enlace: "Cargar gastos" };
    if (campo.startsWith("region_fiscal_no_resuelta"))
      return { texto: `La provincia «${dentro}» no está asociada a ninguna comunidad autónoma, así que no se sabe qué ITP aplicar`, ir: "/mercado", enlace: "Revisar configuración" };
    if (campo.startsWith("gasto_adquisicion"))
      return { texto: `Falta el valor del gasto de adquisición «${dentro}»`, ir: "/mercado", enlace: "Cargar gastos" };
    if (campo === "benchmark_alquiler")
      return { texto: "Falta el €/m² de alquiler medio de la zona: sin él no hay renta ni rentabilidad", ir: "/mercado", enlace: "Cargar benchmarks" };
    if (campo === "benchmark_venta")
      return { texto: "Falta el €/m² de venta medio de la zona: sin él no hay descuento de mercado", ir: "/mercado", enlace: "Cargar benchmarks" };
    if (campo === "tipo_interes_anual")
      return { texto: "Falta el tipo de interés hipotecario del país: sin él no hay cuota ni cashflow", ir: "/mercado", enlace: "Configurar mercado" };
    if (campo.startsWith("tipo_cambio"))
      return { texto: `Falta el tipo de cambio ${dentro}, necesario para normalizar las divisas`, ir: "/mercado", enlace: "Cargar tipo de cambio" };
    if (campo === "tiene_confotur[desconocido]")
      return { texto: "Sin confirmar si el inmueble está acogido a CONFOTUR. El cálculo aplica el impuesto de transferencia mientras tanto" };
    if (campo === "conversion_referencia")
      return { texto: "La conversión a moneda de referencia quedó incompleta (falta una tasa)", ir: "/mercado", enlace: "Cargar tipo de cambio" };
    if (campo === "precio") return { texto: "El anuncio no trae precio: sin él no se puede calcular nada" };
    if (campo === "superficie") return { texto: "El anuncio no trae superficie: sin ella no se puede calcular nada" };
    return { texto: campo };
  };

  return (
    <div className="aparecer rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 shadow-elev-1">
      <div className="flex items-center gap-2 text-warning text-[13px] font-semibold uppercase tracking-wide">
        <IconoAviso /> Qué falta para puntuar este inmueble
      </div>
      <ul className="mt-2 space-y-1.5">
        {faltantes.map((c) => {
          const e = explicar(c);
          return (
            <li key={c} className="flex flex-wrap items-baseline gap-x-2 text-[13px] text-muted leading-relaxed">
              <span className="text-faint cifra text-[11px] shrink-0">{c}</span>
              <span>{e.texto}.</span>
              {e.ir && (
                <Link to={e.ir} className="text-accent hover:underline">{e.enlace} →</Link>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Dato({ k, v }: { k: string; v: any }) {
  return (
    <div className="flex justify-between gap-4 py-1.5">
      <dt className="text-muted">{k}</dt>
      <dd className="text-fg text-right">{v}</dd>
    </div>
  );
}

function Senales({ titulo, codigos, tono }: { titulo: string; codigos?: string[]; tono: "danger" | "positive" }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wider text-faint mb-1.5">{titulo}</div>
      {codigos?.length ? (
        <div className="flex flex-wrap gap-1.5">
          {codigos.map((c) => <Chip key={c} tono={tono}>{c}</Chip>)}
        </div>
      ) : <span className="text-sm text-faint">—</span>}
    </div>
  );
}

/** Auditoría de cifra pulsable. El `title` nativo no existe en táctil (§11.7): en un
 *  móvil la trazabilidad del número era inalcanzable. Ahora se abre un panel. */
function PanelMetricas({ metricas }: { metricas: any }) {
  const [sel, setSel] = useState<string | null>(null);
  const entradas = Object.entries(metricas.metricas || {});
  const auditoria = sel ? metricas.inputs_auditoria?.[sel] : null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 md:gap-2.5">
      {entradas.map(([k, v]) => {
        const activa = sel === k;
        return (
          <button
            key={k}
            type="button"
            onClick={() => setSel(activa ? null : k)}
            aria-expanded={activa}
            className={`text-left border rounded-md p-2.5 min-h-[56px] shadow-elev-1
              transition-[border-color,background-color,box-shadow,transform] duration-150 active:translate-y-px ${
              activa
                ? "border-accent/60 bg-accent/10"
                : "border-line bg-elevated/40 hover:border-muted/40 hover:shadow-elev-2"
            }`}
          >
            <div className="text-[11px] text-faint uppercase tracking-wide truncate">{k}</div>
            <div className="cifra text-[15px] text-fg mt-0.5">{fmtMetrica(v)}</div>
          </button>
        );
      })}

      {sel && (
        <div className="col-span-full aparecer rounded-md border border-accent/40 bg-elevated/60 p-3 shadow-elev-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[11px] uppercase tracking-wider text-accent">{sel}</div>
              <div className="cifra text-sm text-fg mt-1 break-all">
                valor exacto: {String(metricas.metricas?.[sel])}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setSel(null)}
              aria-label="Cerrar auditoría"
              className="shrink-0 h-8 w-8 -mt-1 -mr-1 inline-flex items-center justify-center rounded-md text-muted hover:text-fg hover:bg-elevated transition"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
          {auditoria && Object.keys(auditoria).length > 0 ? (
            <dl className="mt-2.5 text-xs divide-y divide-line/70 border-t border-line/70">
              {Object.entries(auditoria).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 py-1.5">
                  <dt className="text-muted shrink-0">{k}</dt>
                  <dd className="cifra text-fg text-right break-all">{String(v)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-2 text-xs text-faint">Sin inputs de auditoría registrados para esta métrica.</p>
          )}
        </div>
      )}

      {metricas.conversion_parcial && (
        <div className="col-span-full text-xs text-warning">
          Conversión a moneda de referencia incompleta (falta un tipo de cambio).
        </div>
      )}
    </div>
  );
}

/** Tooltip de gráfico: mismo objeto flotante que el resto de la app (elevación 3,
 *  cifra en monoespaciada). El de serie de recharts es genérico y desentona. */
function TooltipSobrio({
  active, payload, label, formato,
}: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-line bg-surface px-2.5 py-2 shadow-elev-3">
      <div className="text-[11px] uppercase tracking-wider text-faint">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="cifra text-[13px] text-fg mt-0.5">
          {formato ? formato(p.value) : p.value}
        </div>
      ))}
    </div>
  );
}

function DesgloseChart({ desglose }: { desglose: any }) {
  const { tema } = useTema();
  const esMovil = useEsMovil();
  const c = coloresGrafico(tema);
  const datos = useMemo(
    () =>
      Object.entries(desglose.componentes || {})
        .filter(([, x]: any) => x.calculable)
        .map(([nombre, x]: any) => ({ nombre, contribucion: Number(x.contribucion || 0) })),
    [desglose],
  );
  // Jerarquía dentro del gráfico: el componente que más aporta al score va en el
  // acento pleno y el resto en su versión tenue. Sin leyenda: se lee solo.
  const maxima = Math.max(...datos.map((d) => d.contribucion), 0);
  // En móvil los nombres de componente (rentabilidad_neta…) no caben en 132px:
  // se recorta el eje y se acorta la etiqueta, o el gráfico se come el ancho.
  const anchoEje = esMovil ? 92 : 132;
  const tamTexto = esMovil ? 10 : 11;
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, datos.length * (esMovil ? 30 : 34))}>
      <BarChart data={datos} layout="vertical" margin={{ left: 0, right: esMovil ? 8 : 16, top: 4, bottom: 4 }}>
        <CartesianGrid horizontal={false} stroke={c.grid} />
        <XAxis type="number" stroke={c.eje} tick={{ fontSize: tamTexto, fill: c.eje }} tickLine={false} axisLine={{ stroke: c.grid }} />
        <YAxis
          type="category"
          dataKey="nombre"
          width={anchoEje}
          tick={{ fontSize: tamTexto, fill: c.eje }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: string) => (esMovil && v.length > 13 ? `${v.slice(0, 12)}…` : v)}
        />
        <Tooltip
          cursor={{ fill: c.grid, opacity: 0.4 }}
          content={<TooltipSobrio formato={(v: number) => `${Number(v).toFixed(2)} pts`} />}
        />
        <Bar
          dataKey="contribucion"
          radius={[0, 3, 3, 0]}
          barSize={esMovil ? 13 : 16}
          animationDuration={450}
          animationEasing="ease-out"
        >
          {datos.map((d) => (
            <Cell key={d.nombre} fill={d.contribucion === maxima ? c.barra : c.barraTenue} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function HistoricoChart({ puntos, moneda }: { puntos: any[]; moneda?: string }) {
  const { tema } = useTema();
  const esMovil = useEsMovil();
  const c = coloresGrafico(tema);
  // El repositorio ya devuelve el histórico en orden cronológico ascendente:
  // no reordenar, o el eje de tiempo leería al revés y una bajada parecería subida.
  const datos = puntos.map((p) => ({
    fecha: new Date(p.fecha_detectada).toLocaleDateString("es-ES", { day: "2-digit", month: "short" }),
    precio: Number(p.precio),
  }));
  return (
    <ResponsiveContainer width="100%" height={esMovil ? 190 : 220}>
      <LineChart data={datos} margin={{ left: 0, right: esMovil ? 8 : 16, top: 8, bottom: 4 }}>
        <CartesianGrid stroke={c.grid} vertical={false} />
        <XAxis dataKey="fecha" stroke={c.eje} tick={{ fontSize: esMovil ? 10 : 11, fill: c.eje }} tickLine={false} axisLine={{ stroke: c.grid }} minTickGap={esMovil ? 24 : 5} />
        {/* Serie de precios: escala ajustada al dato (con holgura), no anclada a 0,
            o una bajada del 10% se vería plana. Los rótulos del eje van siempre.
            En móvil se abrevian a miles (145k) para que quepan en el eje. */}
        <YAxis stroke={c.eje} tick={{ fontSize: esMovil ? 10 : 11, fill: c.eje }} tickLine={false} axisLine={false}
          width={esMovil ? 44 : 64}
          domain={[(min: number) => min * 0.96, (max: number) => max * 1.04]}
          tickFormatter={(v) =>
            esMovil
              ? `${Math.round(Number(v) / 1000)}k`
              : Number(v).toLocaleString("es-ES", { maximumFractionDigits: 0 })
          } />
        <Tooltip
          cursor={{ stroke: c.grid, strokeWidth: 1 }}
          content={<TooltipSobrio formato={(v: number) => `${Number(v).toLocaleString("es-ES")} ${moneda || ""}`.trim()} />}
        />
        <Line
          type="monotone"
          dataKey="precio"
          stroke={c.linea}
          strokeWidth={2}
          dot={{ r: 2.5, fill: c.linea }}
          activeDot={{ r: 4 }}
          animationDuration={500}
          animationEasing="ease-out"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
