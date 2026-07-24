import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import {
  Aviso, Boton, Card, Esqueleto, IconoAviso, Vacio, fmtCantidad, fmtFechaHora, paso,
} from "../ui";

/** USD con 4 decimales: los importes son de céntimos y redondear a 2 los borra. */
function usd(v: unknown): string {
  const n = Number(v ?? 0);
  if (Number.isNaN(n)) return "—";
  return `$${n.toLocaleString("es-ES", { minimumFractionDigits: 4, maximumFractionDigits: 4 })}`;
}

const ETIQUETA_FUENTE: Record<string, string> = {
  ANALISTA: "Analista cualitativo",
  OPENCLAW: "OpenClaw (jobs de extracción)",
  OPENCLAW_CONVERSACION: "OpenClaw (conversaciones directas)",
};

/** Miles con separador, para tokens. */
function tk(v: unknown): string {
  const n = Number(v ?? 0);
  return Number.isNaN(n) ? "—" : n.toLocaleString("es-ES");
}

export default function Costes() {
  const [resumen, setResumen] = useState<any>(null);
  const [porDia, setPorDia] = useState<any[]>([]);
  const [porJob, setPorJob] = useState<any[]>([]);
  const [porInmueble, setPorInmueble] = useState<any[]>([]);
  const [precios, setPrecios] = useState<any[]>([]);
  const [sesiones, setSesiones] = useState<any>(null);
  const [cargando, setCargando] = useState(true);
  const [msg, setMsg] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [sincronizando, setSincronizando] = useState(false);

  const cargar = () => {
    setCargando(true);
    Promise.all([
      api.get("/api/costes/resumen").then(setResumen),
      api.get("/api/costes/por-dia?dias=30").then(setPorDia),
      api.get("/api/costes/por-job?limite=25").then(setPorJob),
      api.get("/api/costes/por-inmueble?limite=25").then(setPorInmueble),
      api.get("/api/costes/precios").then(setPrecios),
      api.get("/api/costes/sesiones").then(setSesiones).catch(() => setSesiones(null)),
    ]).catch(() => {}).finally(() => setCargando(false));
  };
  useEffect(() => { cargar(); }, []);

  const sincronizarSesiones = async () => {
    setSincronizando(true);
    try {
      const r = await api.post("/api/costes/sesiones/sincronizar");
      setMsg(r.legible
        ? `${r.sesiones} sesiones leídas · ${r.nuevas_anotaciones} apuntes nuevos ($${Number(r.coste_usd || 0).toFixed(4)}).`
        : `No se pudieron leer las sesiones: ${r.aviso || "el adaptador no las expone"}`);
      cargar();
    } catch (e) {
      setMsg(`Error leyendo sesiones: ${e}`);
    } finally { setSincronizando(false); }
  };

  const guardarUmbral = async (clave: string, valor: string) => {
    setGuardando(true);
    try {
      await api.put("/api/costes/umbrales", { [clave]: valor });
      setMsg("Umbral guardado.");
      cargar();
    } finally { setGuardando(false); }
  };

  const guardarTope = async (valor: string) => {
    setGuardando(true);
    try {
      await api.put("/api/costes/tope", { tope_gasto_diario_usd: valor });
      setMsg("Tope guardado.");
      cargar();
    } finally { setGuardando(false); }
  };

  if (cargando && !resumen) return <EsqueletoCostes />;

  const total = resumen?.total || {};
  const umbrales = resumen?.umbrales || {};
  const fuentes: any[] = resumen?.por_fuente || [];
  const sinDatos = Number(total.llamadas || 0) === 0;

  return (
    <div className="space-y-4">
      {umbrales.tope_alcanzado && (
        <div className="aparecer rounded-lg border border-danger/60 bg-danger/15 px-4 py-3 shadow-elev-2">
          <div className="flex items-center gap-2 text-danger text-[13px] font-semibold uppercase tracking-wide">
            <IconoAviso /> Tope de gasto alcanzado — no se despacha trabajo nuevo
          </div>
          <p className="text-[13px] text-muted mt-1 leading-relaxed">
            Hoy llevas <strong className="text-fg font-medium">{usd(umbrales.gasto_hoy_usd)}</strong> y el
            tope diario está en {usd(umbrales.tope_diario_usd)}. Los jobs de OpenClaw no se lanzan y los
            lotes del analista se detienen limpiamente entre inmuebles (nunca a mitad de uno).
            Súbelo abajo si quieres continuar hoy.
          </p>
        </div>
      )}

      {(umbrales.supera_diario || umbrales.supera_total) && (
        <div className="aparecer rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 shadow-elev-1">
          <div className="flex items-center gap-2 text-danger text-[13px] font-semibold uppercase tracking-wide">
            <IconoAviso /> Umbral de gasto superado
          </div>
          <p className="text-[13px] text-muted mt-1 leading-relaxed">
            {umbrales.supera_diario && (
              <>Hoy llevas <strong className="text-fg font-medium">{usd(umbrales.gasto_hoy_usd)}</strong>, por
              encima del umbral diario de {usd(umbrales.umbral_diario_usd)}. </>
            )}
            {umbrales.supera_total && (
              <>El acumulado es <strong className="text-fg font-medium">{usd(umbrales.gasto_total_usd)}</strong>,
              por encima de {usd(umbrales.umbral_total_usd)}. </>
            )}
            Esto solo avisa: no corta la ejecución.
          </p>
        </div>
      )}

      {/* El punto ciego. Va ARRIBA y en tono de peligro porque envenena la cifra
          que más se mira: si el gasto de conversación no entra, «gasto total» no
          es el gasto total, y quien lo lea creerá que controla lo que no controla. */}
      {sesiones && !sesiones.contabilizado && (
        <div className="aparecer rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 shadow-elev-1">
          <div className="flex items-center gap-2 text-danger text-[13px] font-semibold uppercase tracking-wide">
            <IconoAviso /> «Gasto total» no es todo tu gasto
          </div>
          <p className="text-[13px] text-muted mt-1 leading-relaxed">
            Aquí solo está lo que pasa por el sistema: el analista y los jobs de OpenClaw.
            Tus <strong className="text-fg font-medium">conversaciones directas con el agente</strong>{" "}
            (por terminal con <span className="cifra text-xs">openclaw agent</span>, o por Telegram)
            gastan igual y <strong className="text-fg font-medium">no están contabilizadas</strong>.
            No es un gasto menor: una sesión con 59 mensajes de historial cuesta ~76.500 tokens de
            escritura de caché <em>en cada mensaje</em> — unos $0,19 por cosa que escribas, y subiendo.
            Para incorporarlo, el adaptador tiene que poder leer los ficheros de sesión: pulsa
            «Leer sesiones ahora» abajo para comprobarlo.
          </p>
        </div>
      )}

      {msg && <Aviso alCerrar={() => setMsg("")}>{msg}</Aviso>}

      {/* Cabecera: las cifras que se miran primero */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Cifra
          titulo="Gasto total"
          valor={usd(total.coste_usd)}
          detalle={sesiones && !sesiones.contabilizado
            ? `${fmtCantidad(total.llamadas)} llamadas · sin conversaciones`
            : `${fmtCantidad(total.llamadas)} llamadas`}
        />
        <Cifra titulo="Hoy" valor={usd(umbrales.gasto_hoy_usd)} detalle={`umbral ${usd(umbrales.umbral_diario_usd)}`}
               alerta={umbrales.supera_diario} />
        <Cifra titulo="Escritura de caché" valor={fmtCantidad(total.tokens_cache_write)}
               detalle="tokens · 1,25× la entrada" />
        <Cifra titulo="Lectura de caché" valor={fmtCantidad(total.tokens_cache_read)}
               detalle="tokens · 0,1× la entrada" />
      </div>

      {sinDatos && (
        <Card titulo="Sin gasto registrado todavía">
          <Vacio variante="panel" titulo="El libro de gasto está vacío">
            Solo se registra lo que ocurre a partir de ahora: el consumo anterior a esta
            versión no quedó anotado en ninguna parte. Ejecuta un análisis o un job y
            aparecerá aquí desglosado.
          </Vacio>
        </Card>
      )}

      {/* Por fuente: la pregunta central — ¿quién gasta? */}
      <Card titulo="Por fuente" subtitulo="analista (backend) vs OpenClaw (agente)">
        {fuentes.length === 0 ? (
          <Vacio titulo="Sin movimientos">Aún no hay gasto de ninguna de las dos fuentes.</Vacio>
        ) : (
          <div className="space-y-3">
            {fuentes.map((f) => {
              const pct = Number(total.coste_usd) > 0
                ? (Number(f.coste_usd) / Number(total.coste_usd)) * 100 : 0;
              return (
                <div key={f.fuente}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-sm text-fg">{ETIQUETA_FUENTE[f.fuente] || f.fuente}</span>
                    <span className="cifra text-sm text-fg">{usd(f.coste_usd)}</span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-line overflow-hidden">
                    <div className="h-full rounded-full bg-accent transition-[width] duration-300 ease-sal"
                         style={{ width: `${Math.max(2, pct)}%` }} />
                  </div>
                  <div className="mt-1 text-xs text-faint">
                    entrada {fmtCantidad(f.tokens_entrada)} · salida {fmtCantidad(f.tokens_salida)} ·
                    {" "}caché escritura {fmtCantidad(f.tokens_cache_write)} · lectura {fmtCantidad(f.tokens_cache_read)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <SesionesAgente
        datos={sesiones}
        ocupado={sincronizando}
        onSincronizar={sincronizarSesiones}
        onUmbral={async (v) => {
          await api.put("/api/costes/umbral-sesion", { umbral_tokens_sesion: v });
          setMsg("Umbral de sesión guardado.");
          cargar();
        }}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <Card titulo="Por día" subtitulo="últimos 30 días">
          {porDia.length === 0 ? <Vacio titulo="Sin gasto en el periodo" /> : (
            <div className="tabla-scroll">
              <table>
                <thead><tr><th>Día</th><th>Fuente</th><th className="text-right">Coste</th></tr></thead>
                <tbody className="escalonado">
                  {porDia.map((d, i) => (
                    <tr key={`${d.dia}-${d.fuente}`} {...paso(i)}>
                      <td className="cifra text-muted text-xs">{String(d.dia).slice(0, 10)}</td>
                      <td className="text-muted text-xs">{ETIQUETA_FUENTE[d.fuente] || d.fuente}</td>
                      <td className="text-right cifra text-fg">{usd(d.coste_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card titulo="Por job" subtitulo="coste de cada ejecución">
          {porJob.length === 0 ? <Vacio titulo="Sin jobs con gasto" /> : (
            <div className="tabla-scroll">
              <table>
                <thead><tr><th>Job</th><th>Estado</th><th className="text-right">Coste</th></tr></thead>
                <tbody className="escalonado">
                  {porJob.map((j, i) => (
                    <tr key={j.job_id} {...paso(i)}>
                      <td className="cifra text-xs text-muted">{String(j.job_id).slice(0, 8)}</td>
                      <td className="text-xs text-muted">{j.estado || "—"}</td>
                      <td className="text-right cifra text-fg">{usd(j.coste_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <Card titulo="Por inmueble analizado" subtitulo="los más caros primero">
        {porInmueble.length === 0 ? <Vacio titulo="Ningún inmueble analizado con gasto registrado" /> : (
          <div className="tabla-scroll">
            <table>
              <thead>
                <tr><th>Inmueble</th><th className="text-right">Entrada</th><th className="text-right">Salida</th><th className="text-right">Coste</th></tr>
              </thead>
              <tbody className="escalonado">
                {porInmueble.map((r, i) => (
                  <tr key={r.inmueble_id} {...paso(i)}>
                    <td className="max-w-sm">
                      <Link className="text-fg hover:text-accent transition-colors truncate block"
                            to={`/inmueble/${r.inmueble_id}`}>
                        {r.titulo || "(sin título)"}
                      </Link>
                      <span className="text-xs text-faint">{[r.ciudad, r.pais].filter(Boolean).join(" · ")}</span>
                    </td>
                    <td className="text-right cifra text-faint">{fmtCantidad(r.tokens_entrada)}</td>
                    <td className="text-right cifra text-faint">{fmtCantidad(r.tokens_salida)}</td>
                    <td className="text-right cifra text-fg">{usd(r.coste_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card titulo="Umbrales de aviso" subtitulo="solo avisan; no cortan la ejecución">
        <div className="flex flex-wrap items-end gap-3">
          <UmbralCampo etiqueta="Diario (USD)" valorInicial={umbrales.umbral_diario_usd}
                       ocupado={guardando} onGuardar={(v) => guardarUmbral("umbral_gasto_diario_usd", v)} />
          <UmbralCampo etiqueta="Total (USD)" valorInicial={umbrales.umbral_total_usd}
                       ocupado={guardando} onGuardar={(v) => guardarUmbral("umbral_gasto_total_usd", v)} />
        </div>
      </Card>

      <Card titulo="Tope de gasto diario" subtitulo="esto SÍ corta: por encima no se despacha trabajo nuevo">
        <p className="text-[13px] text-muted leading-relaxed mb-3">
          Arranca en un valor conservador ({usd(umbrales.tope_diario_usd)}): un job típico de
          OpenClaw se estimó en ~$1,75, así que deja pasar aproximadamente uno al día. Súbelo a
          conciencia. El corte es «no empezar», nunca «matar a mitad»: un job en vuelo termina.
        </p>
        <UmbralCampo etiqueta="Tope diario (USD)" valorInicial={umbrales.tope_diario_usd}
                     ocupado={guardando} onGuardar={guardarTope} />
      </Card>

      <Card titulo="Precios por modelo" subtitulo="USD por millón de tokens · editables porque cambian">
        <div className="tabla-scroll">
          <table>
            <thead>
              <tr>
                <th>Modelo</th><th className="text-right">Entrada</th><th className="text-right">Salida</th>
                <th className="text-right">Caché escr.</th><th className="text-right">Caché lect.</th><th>Fuente</th>
              </tr>
            </thead>
            <tbody>
              {precios.map((p) => (
                <tr key={p.modelo}>
                  <td className="text-fg">{p.modelo}</td>
                  <td className="text-right cifra">{usd(p.usd_entrada_por_m)}</td>
                  <td className="text-right cifra">{usd(p.usd_salida_por_m)}</td>
                  <td className="text-right cifra text-warning">{usd(p.usd_cache_write_por_m)}</td>
                  <td className="text-right cifra text-positive">{usd(p.usd_cache_read_por_m)}</td>
                  <td className="text-xs text-faint max-w-xs truncate" title={p.fuente || ""}>{p.fuente || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <p className="text-xs text-faint leading-relaxed">
        {resumen?.registro_desde ? (
          <>
            <strong className="text-muted">El libro de gasto empieza el{" "}
            {fmtFechaHora(resumen.registro_desde)}.</strong>{" "}
            Lo consumido antes de esa fecha no quedó anotado en ninguna parte y no se puede
            reconstruir: «gasto total» significa «desde que existe el libro», no «desde siempre».{" "}
          </>
        ) : (
          <><strong className="text-muted">Aún no hay ningún apunte.</strong>{" "}
          El libro se estrena con la primera llamada. Lo gastado antes de desplegar esta versión
          no quedó registrado.{" "}</>
        )}
        El coste de cada llamada se congela con el precio vigente en ese momento: cambiar un
        precio no reescribe el histórico.{" "}
        {sesiones && !sesiones.contabilizado && (
          <strong className="text-muted">
            Y hoy falta una fuente: el gasto de tus conversaciones directas con el agente no está
            entrando en el libro.
          </strong>
        )}
      </p>
    </div>
  );
}

/** Conversaciones directas con el agente: el gasto que el libro no veía.
 *
 *  Lo que importa aquí NO es el acumulado (ese ya está gastado) sino
 *  `tokens_proximo_mensaje`: lo que costará el siguiente mensaje de esa sesión.
 *  Es la única cifra sobre la que aún se puede actuar — limpiando la sesión. */
function SesionesAgente({ datos, ocupado, onSincronizar, onUmbral }: {
  datos: any; ocupado: boolean;
  onSincronizar: () => void; onUmbral: (v: string) => void;
}) {
  const sesiones: any[] = datos?.sesiones || [];
  const gordas: any[] = datos?.sesiones_a_limpiar || [];
  const umbral = datos?.umbral_tokens_sesion;

  return (
    <Card
      titulo="Conversaciones con el agente"
      subtitulo="gasto de hablar con OpenClaw fuera del sistema (terminal, Telegram)"
      acciones={
        <Boton variante="secundario" cargando={ocupado} onClick={onSincronizar}>
          {ocupado ? "Leyendo" : "Leer sesiones ahora"}
        </Boton>
      }
    >
      {gordas.length > 0 && (
        <div className="mb-3 rounded-md border border-warning/40 bg-warning/10 p-3">
          <div className="flex items-center gap-2 text-warning text-[13px] font-semibold uppercase tracking-wide">
            <IconoAviso /> {gordas.length === 1 ? "1 sesión conviene limpiarla" : `${gordas.length} sesiones conviene limpiarlas`}
          </div>
          <p className="text-[13px] text-muted mt-1 leading-relaxed">
            Pasan de {tk(umbral)} tokens por mensaje. Una sesión cobra su historial entero cada vez
            que escribes, así que solo sube. Empezar una sesión nueva devuelve el coste al mínimo:
            el procedimiento está en <span className="cifra text-xs">docs/OPENCLAW_SESIONES.md</span>.
          </p>
        </div>
      )}

      {sesiones.length === 0 ? (
        <Vacio titulo="Ninguna sesión leída todavía">
          El adaptador expone las sesiones en <span className="cifra text-xs">GET /sesiones</span>,
          leyendo <span className="cifra text-xs">/root/.openclaw/agents/*/sessions/*.jsonl</span>.
          Si no aparece nada, o el adaptador es de una versión anterior, o no puede leer esa ruta
          (ajusta <span className="cifra text-xs">OPENCLAW_SESIONES_PATH</span>). Mientras tanto, el
          gasto de tus conversaciones sigue sin contabilizarse.
        </Vacio>
      ) : (
        <div className="tabla-scroll">
          <table>
            <thead>
              <tr>
                <th>Sesión</th>
                <th className="text-right">Próximo mensaje</th>
                <th className="text-right">Turnos</th>
                <th className="text-right">Caché escr.</th>
                <th>Última actividad</th>
              </tr>
            </thead>
            <tbody className="escalonado">
              {sesiones.map((s, i) => (
                <tr key={s.id} {...paso(i)} className={s.supera_umbral ? "bg-warning/5" : ""}>
                  <td className="max-w-xs">
                    <div className="cifra text-xs text-fg truncate" title={s.id}>{s.id}</div>
                    <div className="text-[11px] text-faint">{[s.agente, s.modelo].filter(Boolean).join(" · ") || "—"}</div>
                  </td>
                  <td className={`text-right cifra ${s.supera_umbral ? "text-warning" : "text-fg"}`}>
                    {tk(s.tokens_proximo_mensaje)}
                  </td>
                  <td className="text-right cifra text-muted">{tk(s.turnos)}</td>
                  <td className="text-right cifra text-faint">{tk(s.tokens_cache_write)}</td>
                  <td className="text-xs text-muted whitespace-nowrap">{fmtFechaHora(s.modificada_en)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <UmbralCampo etiqueta="Avisar por encima de (tokens/mensaje)"
                     valorInicial={umbral != null ? String(umbral) : ""}
                     ocupado={ocupado} onGuardar={onUmbral} />
      </div>
      <p className="mt-3 text-xs text-faint leading-relaxed">
        Las sesiones de los jobs (<span className="cifra">inmobiliaria:job:…</span>) no salen aquí:
        ya se contabilizan como gasto del job y contarlas dos veces inflaría el total.
      </p>
    </Card>
  );
}

function Cifra({ titulo, valor, detalle, alerta }: {
  titulo: string; valor: string; detalle?: string; alerta?: boolean;
}) {
  return (
    <div className={`rounded-lg border bg-surface shadow-elev-1 p-3 ${alerta ? "border-danger/50" : "border-line"}`}>
      <div className="text-[11px] font-medium uppercase tracking-wider text-faint">{titulo}</div>
      <div className={`cifra text-[22px] font-semibold tracking-tight mt-0.5 ${alerta ? "text-danger" : "text-fg"}`}>
        {valor}
      </div>
      {detalle && <div className="text-[11px] text-faint mt-0.5">{detalle}</div>}
    </div>
  );
}

function UmbralCampo({ etiqueta, valorInicial, ocupado, onGuardar }: {
  etiqueta: string; valorInicial?: string; ocupado: boolean; onGuardar: (v: string) => void;
}) {
  const [v, setV] = useState(valorInicial ?? "");
  useEffect(() => { setV(valorInicial ?? ""); }, [valorInicial]);
  return (
    <div>
      <label className="etiqueta">{etiqueta}</label>
      <div className="flex gap-2">
        <input value={v} onChange={(e) => setV(e.target.value)} className="campo w-28 cifra text-right" />
        <Boton variante="secundario" cargando={ocupado} onClick={() => onGuardar(v)}>Guardar</Boton>
      </div>
    </div>
  );
}

function EsqueletoCostes() {
  return (
    <div className="space-y-4" aria-busy="true">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="rounded-lg border border-line bg-surface shadow-elev-1 p-3 space-y-2">
            <Esqueleto className="h-2.5 w-20" />
            <Esqueleto className="h-6 w-24" />
            <Esqueleto className="h-2.5 w-16" />
          </div>
        ))}
      </div>
      {[0, 1].map((i) => (
        <div key={i} className="rounded-lg border border-line bg-surface shadow-elev-1 overflow-hidden">
          <div className="h-11 border-b border-line flex items-center px-4"><Esqueleto className="h-3.5 w-32" /></div>
          <div className="p-4 space-y-2">
            {[0, 1, 2].map((j) => <Esqueleto key={j} className="h-4 w-full" />)}
          </div>
        </div>
      ))}
    </div>
  );
}
