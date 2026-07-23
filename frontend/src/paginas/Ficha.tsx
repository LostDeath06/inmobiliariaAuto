import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { coloresGrafico, useTema } from "../tema";
import { AvisoProvisional, BadgeCalidad, BadgeScore, Boton, Card, Chip, IconoAviso, Vacio, fmtDinero, fmtMetrica, useEsMovil } from "../ui";

export default function Ficha() {
  const { id } = useParams();
  const [datos, setDatos] = useState<any>(null);
  const [perfiles, setPerfiles] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  const cargar = () => api.get(`/api/inmuebles/${id}`).then(setDatos).catch((e) => setError(String(e)));
  useEffect(() => { cargar(); }, [id]);
  useEffect(() => {
    api.get("/api/perfiles").then((ps: any[]) =>
      setPerfiles(Object.fromEntries(ps.map((p) => [p.id, p.nombre]))),
    ).catch(() => {});
  }, []);

  if (error) return <div className="text-sm text-danger bg-danger/10 border border-danger/30 rounded-md px-3 py-2">{error}</div>;
  if (!datos) return <Vacio>Cargando…</Vacio>;

  const { inmueble, metricas, analisis, scores, historico_precios, zona } = datos;
  const noReconocidas: string[] = analisis?.senales_no_reconocidas || [];
  const zonaTuristica = zona?.perfil_zona === "TURISTICA";

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
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
            <Boton className="w-full sm:w-auto" onClick={() => api.post(`/api/inmuebles/${id}/recalcular`).then(cargar)}>
              Recalcular
            </Boton>
          </div>
        </div>
      </div>

      {zonaTuristica && (
        <div className="rounded-lg border border-accent/40 bg-accent/10 px-4 py-3">
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
        <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3">
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        <Card titulo="Datos">
          <dl className="text-sm divide-y divide-line/70">
            <Dato k="Precio" v={<span className="cifra text-fg">{fmtDinero(inmueble.precio, inmueble.moneda)}</span>} />
            <Dato k="Superficie útil" v={<span className="cifra">{inmueble.superficie_util_m2 ? `${inmueble.superficie_util_m2} m²` : "—"}</span>} />
            <Dato k="Superficie construida" v={<span className="cifra">{inmueble.superficie_construida_m2 ? `${inmueble.superficie_construida_m2} m²` : "—"}</span>} />
            <Dato k="Habitaciones" v={<span className="cifra">{inmueble.habitaciones ?? "—"}</span>} />
            <Dato k="Tipo anunciante" v={inmueble.tipo_anunciante || "—"} />
            <Dato k="Calidad del dato" v={<BadgeCalidad estado={inmueble.estado_calidad} />} />
          </dl>
          {inmueble.posible_duplicado_cross_portal && (
            <p className="text-xs text-muted mt-3">Marcado como posible duplicado en otro portal.</p>
          )}
        </Card>

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
            {scores.length === 0 && <Vacio>Sin scores</Vacio>}
          </div>
        </Card>

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
          ) : <Vacio>Sin análisis (pendiente o fallido)</Vacio>}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <Card titulo="Desglose del score" subtitulo="contribución de cada componente">
          {scores[0]?.desglose?.componentes ? (
            <DesgloseChart desglose={scores[0].desglose} />
          ) : <Vacio>Sin desglose disponible</Vacio>}
        </Card>

        <Card titulo="Histórico de precios" subtitulo="moneda nativa del anuncio">
          {historico_precios?.length >= 2 ? (
            <HistoricoChart puntos={historico_precios} moneda={inmueble.moneda} />
          ) : <Vacio>Un solo punto de precio: sin serie todavía.</Vacio>}
        </Card>
      </div>

      <Card titulo="Métricas financieras" subtitulo="motor determinista · mantén pulsada una cifra para ver su fórmula e inputs">
        {metricas ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 md:gap-2.5">
            {Object.entries(metricas.metricas || {}).map(([k, v]) => (
              <div
                key={k}
                className="border border-line rounded-md p-2.5 bg-elevated/40 hover:border-muted/40 transition cursor-help"
                title={`valor exacto: ${v}\n\n${JSON.stringify(metricas.inputs_auditoria?.[k] || {}, null, 2)}`}
              >
                <div className="text-[11px] text-faint uppercase tracking-wide truncate">{k}</div>
                <div className="cifra text-[15px] text-fg mt-0.5">{fmtMetrica(v)}</div>
              </div>
            ))}
            {metricas.conversion_parcial && (
              <div className="col-span-full text-xs text-warning">
                Conversión a moneda de referencia incompleta (falta un tipo de cambio).
              </div>
            )}
          </div>
        ) : <Vacio>Sin métricas</Vacio>}
      </Card>
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
          contentStyle={{ background: c.superficie, border: `1px solid ${c.grid}`, borderRadius: 8, fontSize: 12, color: c.etiqueta }}
          labelStyle={{ color: c.etiqueta }}
        />
        <Bar dataKey="contribucion" fill={c.barra} radius={[0, 3, 3, 0]} barSize={esMovil ? 13 : 16} />
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
          contentStyle={{ background: c.superficie, border: `1px solid ${c.grid}`, borderRadius: 8, fontSize: 12, color: c.etiqueta }}
          labelStyle={{ color: c.etiqueta }}
          formatter={(v: any) => [`${Number(v).toLocaleString("es-ES")} ${moneda || ""}`.trim(), "Precio"]}
        />
        <Line type="monotone" dataKey="precio" stroke={c.linea} strokeWidth={2} dot={{ r: 2.5, fill: c.linea }} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

