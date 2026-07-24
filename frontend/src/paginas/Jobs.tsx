import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import {
  Aviso, Boton, Card, Chip, Confirmacion, IconoAviso, Vacio,
  fmtDuracion, fmtFechaHora, paso,
} from "../ui";

/** Estados desde los que un job todavía puede pararse — y todavía puede gastar.
 *  Espejo de `despacho.CANCELABLES`: fuera de aquí no hay nada que abortar. */
const CANCELABLES = new Set(["PENDIENTE", "ENVIADO", "EN_PROGRESO"]);

const TONO_ESTADO: Record<string, string> = {
  COMPLETADO: "text-positive border-positive/30 bg-positive/10",
  PARCIAL: "text-warning border-warning/30 bg-warning/10",
  FALLIDO: "text-danger border-danger/30 bg-danger/10",
  CANCELADO: "text-faint border-line bg-elevated",
  EN_PROGRESO: "text-accent border-accent/30 bg-accent/10",
  ENVIADO: "text-accent border-accent/30 bg-accent/10",
  PENDIENTE: "text-muted border-line bg-elevated",
};

function EstadoJob({ estado }: { estado: string }) {
  const tono = TONO_ESTADO[estado] || "text-muted border-line bg-elevated";
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide border ${tono}`}>
      {estado}
    </span>
  );
}

/** Traduce los modos de fallo que ya hemos visto. El mensaje crudo de Pydantic es
 *  exacto pero ilegible de un vistazo; esto dice qué hacer sin salir de la app.
 *  Solo presentación: el motivo real es siempre `error_mensaje`, que va debajo. */
function diagnosticar(error?: string | null): string | null {
  if (!error) return null;
  // OpenClaw devolvió la plantilla de tipos del contrato en vez de rellenarla.
  if (/input_value='\s*(integer|string|boolean|number|array|object)\b/i.test(error)) {
    return (
      "OpenClaw copió la plantilla de tipos del contrato en lugar de rellenarla con datos: " +
      "devolvió literales como «integer (obligatorio)» donde tenía que ir un número. " +
      "El validador lo rechazó entero, así que no entró ningún anuncio. " +
      "Revisa que el agente tenga la versión actual de docs/PROMPT_PARA_OPENCLAW.md " +
      "(el contrato lleva un ejemplo relleno y un aviso explícito sobre esto)."
    );
  }
  if (/Extra inputs are not permitted|extra_forbidden/i.test(error)) {
    return (
      "El JSON traía campos que el contrato no declara. El sistema rechaza campos no " +
      "declarados a propósito: un campo desconocido suele significar que el agente se " +
      "inventó estructura. Comprueba la tabla de tipos del contrato."
    );
  }
  if (/Field required|missing/i.test(error)) {
    return "Faltan campos obligatorios en el JSON. Mira cuáles abajo y contrástalos con la tabla de tipos del contrato.";
  }
  if (/timeout|timed out/i.test(error)) {
    return "OpenClaw no respondió a tiempo. El job no llegó a devolver datos; puedes reintentarlo.";
  }
  return null;
}

/** El motivo del fallo, con su mensaje crudo. Antes solo existía en los logs del
 *  VPS: para enterarse había que abrir una terminal. */
function PanelFallo({ error }: { error: string }) {
  const pista = diagnosticar(error);
  return (
    <div className="rounded-md border border-danger/40 bg-danger/10 p-3 space-y-2">
      <div className="flex items-center gap-2 text-danger text-[13px] font-semibold uppercase tracking-wide">
        <IconoAviso /> Motivo del fallo
      </div>
      {pista && <p className="text-[13px] text-muted leading-relaxed">{pista}</p>}
      <details className="group" open={!pista}>
        <summary className="cursor-pointer text-[11px] uppercase tracking-wider text-faint hover:text-muted select-none">
          Mensaje de validación completo
        </summary>
        <pre className="mt-1.5 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded bg-base/60 p-2 text-[11px] leading-relaxed text-danger cifra">
          {error}
        </pre>
      </details>
    </div>
  );
}

export default function Jobs() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  const [prompt, setPrompt] = useState("");
  const [pegado, setPegado] = useState("");
  const [cuarentena, setCuarentena] = useState<any[]>([]);
  const [noReconocidas, setNoReconocidas] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [msgTono, setMsgTono] = useState<"positive" | "danger">("positive");
  const [ingestando, setIngestando] = useState(false);
  const [reprocesando, setReprocesando] = useState(false);
  const [avisoReproceso, setAvisoReproceso] = useState("");
  const [porCancelar, setPorCancelar] = useState<any>(null);
  const [cancelando, setCancelando] = useState(false);
  const [avisoCancelacion, setAvisoCancelacion] = useState<
    { texto: string; tono: "positive" | "danger" } | null
  >(null);
  const [limpiando, setLimpiando] = useState(false);

  /** Cancelar de verdad: aborta el proceso de OpenClaw, no solo la etiqueta.
   *  Si el adaptador NO confirma que el proceso murió, se dice en tono de
   *  peligro: un "cancelado" tranquilo sobre un agente que sigue gastando es
   *  exactamente el fallo silencioso que este sistema existe para evitar. */
  const cancelar = async (job: any) => {
    setCancelando(true);
    try {
      const r = await api.post(`/api/jobs/${job.id}/cancelar`);
      const gasto = r.gasto_parcial;
      const cola = gasto?.coste_usd
        ? ` Gasto anotado hasta el corte: $${Number(gasto.coste_usd).toFixed(4)}${gasto.parcial ? " (parcial)" : ""}.`
        : " No se pudo leer el gasto del agente: puede que no llegara a reportarlo.";
      setAvisoCancelacion(
        r.proceso_abortado
          ? { tono: "positive", texto: `Job cancelado y proceso de OpenClaw abortado.${cola}` }
          : { tono: "danger", texto:
              `Estado marcado CANCELADO, pero el adaptador NO confirmó que el proceso muriera` +
              `${r.detalle ? ` (${r.detalle})` : ""}. Puede seguir consumiendo tokens: revísalo en el VPS.${cola}` },
      );
      setPorCancelar(null);
      cargar();
    } catch (e) {
      setAvisoCancelacion({ tono: "danger", texto: `No se pudo cancelar: ${e}` });
    } finally {
      setCancelando(false);
    }
  };

  /** Cierra los jobs que llevan una hora colgados. Para el ruido que ya existe:
   *  jobs que el adaptador olvidó al reiniciarse y que nadie va a resolver. */
  const limpiarZombis = async () => {
    setLimpiando(true);
    try {
      const r = await api.post("/api/jobs/limpiar-zombis?minutos=60");
      setAvisoCancelacion({
        tono: "positive",
        texto: r.cerrados === 0
          ? "No hay jobs zombis: ninguno lleva más de 60 minutos sin avanzar."
          : `${r.cerrados} job(s) zombis cerrados como FALLIDO. El backend deja de consultarlos.`,
      });
      cargar();
    } catch (e) {
      setAvisoCancelacion({ tono: "danger", texto: `Error limpiando: ${e}` });
    } finally {
      setLimpiando(false);
    }
  };

  const reprocesar = async () => {
    setReprocesando(true);
    try {
      const r = await api.post("/api/pipeline/reprocesar-sin-analisis");
      setAvisoReproceso(
        r.pendientes === 0
          ? "No hay ningún inmueble sin análisis: todos tienen el suyo."
          : `${r.pendientes} inmuebles reprocesados · ${r.analisis_fallidos} siguen fallando` +
            (r.motivos_fallo?.length ? ` · ${r.motivos_fallo[0]}` : ""),
      );
    } catch (e) {
      setAvisoReproceso(`Error: ${e}`);
    } finally {
      setReprocesando(false);
    }
  };

  const cargar = () => {
    api.get("/api/jobs").then(setJobs).catch(() => {});
    api.get("/api/senales-no-reconocidas").then(setNoReconocidas).catch(() => {});
  };
  useEffect(() => { cargar(); const t = setInterval(cargar, 5000); return () => clearInterval(t); }, []);

  const abrir = async (j: any) => {
    setSel(j); setMsg("");
    const p = await api.get(`/api/jobs/${j.id}/prompt`);
    setPrompt(p.prompt || "");
    setCuarentena(await api.get(`/api/jobs/${j.id}/cuarentena`));
  };

  const enviarManual = async () => {
    setIngestando(true);
    try {
      const sobre = JSON.parse(pegado);
      const r = await api.post(`/api/jobs/${sel.id}/resultado-manual`, sobre);
      setMsgTono("positive");
      setMsg(`Ingesta: ${r.validos} válidos, ${r.cuarentena} en cuarentena, ${r.procesados} procesados.`);
      cargar(); abrir(sel);
    } catch (e) {
      setMsgTono("danger");
      setMsg(`Error: ${e}`);
    } finally { setIngestando(false); }
  };

  // `sel` es la foto del job al pulsar «Abrir»; la lista se refresca cada 5 s.
  // Para el motivo del fallo hace falta la fila viva, o mostraría un estado viejo.
  const selVivo = jobs.find((j) => j.id === sel?.id) || sel;
  const fallidos = jobs.filter((j) => j.estado === "FALLIDO" && j.error_mensaje);

  const vivos = jobs.filter((j) => CANCELABLES.has(j.estado));

  return (
    <div className="space-y-4">
      {avisoCancelacion && (
        <Aviso tono={avisoCancelacion.tono} msSalida={avisoCancelacion.tono === "danger" ? 0 : 8000}
               alCerrar={() => setAvisoCancelacion(null)}>
          {avisoCancelacion.texto}
        </Aviso>
      )}

      {porCancelar && (
        <Confirmacion
          titulo="Cancelar el job en curso"
          etiquetaConfirmar="Sí, cancelar el job"
          ocupado={cancelando}
          onConfirmar={() => cancelar(porCancelar)}
          onCancelar={() => setPorCancelar(null)}
        >
          <p>
            Se abortará el proceso de OpenClaw del job{" "}
            <span className="cifra text-fg">{String(porCancelar.id).slice(0, 8)}</span>{" "}
            ({porCancelar.estado}). <strong className="text-fg font-medium">No se puede deshacer</strong>:
            el trabajo hecho hasta ahora se pierde y no habrá anuncios de este job.
          </p>
          <p>
            Lo ya consumido <strong className="text-fg font-medium">sí se cobra</strong> y queda
            anotado en el libro de costes. Cancelar evita el gasto que falta, no recupera el hecho.
          </p>
        </Confirmacion>
      )}

      {/* Lo primero de la pantalla si algo se rompió: el motivo, sin tener que
          abrir el job ni entrar por SSH a mirar los logs del contenedor. */}
      {fallidos.length > 0 && (
        <Card
          titulo={fallidos.length === 1 ? "1 job fallido" : `${fallidos.length} jobs fallidos`}
          subtitulo="ningún anuncio de estos jobs entró en el sistema"
        >
          <div className="space-y-3 escalonado">
            {fallidos.map((j, i) => (
              <div key={j.id} {...paso(i)}>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="cifra text-[11px] text-faint">{String(j.id).slice(0, 8)}</span>
                  <EstadoJob estado={j.estado} />
                  <Boton variante="fantasma" onClick={() => abrir(j)}>Abrir</Boton>
                </div>
                <PanelFallo error={j.error_mensaje} />
              </div>
            ))}
          </div>
        </Card>
      )}

      {vivos.length > 0 && (
        <Card
          titulo={vivos.length === 1 ? "1 job en curso" : `${vivos.length} jobs en curso`}
          subtitulo="cada uno cuesta dinero mientras corre — se pueden parar aquí"
        >
          <div className="space-y-2 escalonado">
            {vivos.map((j, i) => (
              <div key={j.id} {...paso(i)}
                   className="flex flex-wrap items-center gap-2 py-1.5 border-b border-line/70 last:border-0">
                <span className="cifra text-[11px] text-faint">{String(j.id).slice(0, 8)}</span>
                <EstadoJob estado={j.estado} />
                {/* Se recalcula con el refresco de 5 s de la lista. */}
                <span className="cifra text-xs text-muted">
                  lleva {fmtDuracion(j.iniciado_en || j.created_at, new Date().toISOString())}
                </span>
                <div className="ml-auto">
                  <Boton variante="peligro" onClick={() => setPorCancelar(j)}>Cancelar</Boton>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card
        titulo="Jobs zombis"
        subtitulo="los que quedaron colgados antes de que hubiera timeout"
        acciones={
          <Boton variante="secundario" cargando={limpiando} onClick={limpiarZombis}>
            {limpiando ? "Limpiando" : "Cerrar jobs de más de 60 min"}
          </Boton>
        }
      >
        <p className="text-[13px] text-muted leading-relaxed">
          El adaptador guarda sus jobs <strong className="text-fg font-medium">en memoria</strong>,
          así que un <span className="cifra text-xs">systemctl restart</span> los pierde. El backend,
          que los tenía como <span className="cifra text-xs">EN_PROGRESO</span>, seguía
          consultándolos y recibiendo <span className="cifra text-xs">404</span> indefinidamente.
          Eso ya no pasa con los jobs nuevos: el worker se rinde tras varios 404 seguidos y aplica
          un timeout duro. Esto cierra los que quedaron de antes, para que dejen de ensuciar los logs.
        </p>
      </Card>

      <Card
        titulo="Reprocesar análisis"
        subtitulo="para los inmuebles cuyo análisis cualitativo falló"
        acciones={
          <Boton variante="secundario" cargando={reprocesando} onClick={reprocesar}>
            {reprocesando ? "Reprocesando" : "Reprocesar sin análisis"}
          </Boton>
        }
      >
        <p className="text-[13px] text-muted leading-relaxed">
          El análisis cualitativo se intenta <strong className="text-fg font-medium">siempre</strong>,
          antes de las métricas y sin depender de la configuración de mercado. Así que un
          inmueble sin análisis es uno cuyo análisis <em>falló</em> (API caída, clave incorrecta,
          JSON inválido), no uno pendiente de que cargues datos. Esto lo reintenta en lote,
          sin volver a pedirle nada a OpenClaw.
        </p>
        {avisoReproceso && (
          <div className="mt-3">
            <Aviso tono={avisoReproceso.startsWith("Error") ? "danger" : "positive"}
                   alCerrar={() => setAvisoReproceso("")}>
              {avisoReproceso}
            </Aviso>
          </div>
        )}
      </Card>

      {noReconocidas.length > 0 && (
        <Card
          titulo="Señales fuera de catálogo"
          subtitulo="Claude devolvió códigos que el catálogo del país no contempla — revísalos"
        >
          <div className="space-y-2 escalonado">
            {noReconocidas.map((n, i) => (
              <div key={n.inmueble_id} {...paso(i)} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 sm:gap-4 py-2 border-b border-line/70 last:border-0">
                <Link to={`/inmueble/${n.inmueble_id}`} className="text-fg hover:text-accent transition truncate">
                  {n.titulo || "(sin título)"}
                  <span className="text-faint text-xs ml-2">{[n.ciudad, n.pais].filter(Boolean).join(" · ")}</span>
                </Link>
                <div className="flex flex-wrap gap-1.5 sm:justify-end shrink-0">
                  {(n.senales_no_reconocidas || []).map((c: string) => <Chip key={c} tono="warning">{c}</Chip>)}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <Card titulo="Jobs" subtitulo="auto-refresco cada 5 s">
          <div className="tabla-scroll">
            <table>
              <thead>
                <tr>
                  <th>Estado</th>
                  <th>Inicio</th>
                  <th className="text-right">Duración</th>
                  <th className="text-right">Válidos</th>
                  <th className="text-right">Cuar.</th>
                  <th className="text-right">Coste USD</th>
                  <th></th>
                </tr>
              </thead>
              <tbody className="escalonado">
                {jobs.map((j, i) => (
                  <tr key={j.id} {...paso(i)} className={j.error_mensaje ? "bg-danger/5" : ""}>
                    <td>
                      <EstadoJob estado={j.estado} />
                      {j.error_mensaje && (
                        <div className="text-[11px] text-danger/80 mt-1 max-w-[22rem] truncate" title={j.error_mensaje}>
                          {String(j.error_mensaje).split("\n")[0]}
                        </div>
                      )}
                    </td>
                    <td className="cifra text-muted text-xs whitespace-nowrap">
                      {fmtFechaHora(j.iniciado_en || j.created_at)}
                    </td>
                    <td className="text-right cifra text-muted text-xs whitespace-nowrap">
                      {fmtDuracion(j.iniciado_en || j.created_at, j.finalizado_en)}
                    </td>
                    <td className="text-right cifra text-fg">{j.total_anuncios_validos ?? "—"}</td>
                    <td className="text-right cifra text-muted">{j.total_anuncios_cuarentena ?? "—"}</td>
                    <td className="text-right cifra text-muted">{j.coste_estimado_usd ? Number(j.coste_estimado_usd).toFixed(4) : "—"}</td>
                    <td className="text-right whitespace-nowrap">
                      {CANCELABLES.has(j.estado) && (
                        <Boton variante="peligro" onClick={() => setPorCancelar(j)}
                               title="Aborta el proceso de OpenClaw y deja de gastar">
                          Cancelar
                        </Boton>
                      )}
                      <Boton variante="fantasma" onClick={() => abrir(j)}>Abrir</Boton>
                    </td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr>
                    <td colSpan={7}>
                      <Vacio titulo="Sin jobs todavía">
                        Un job se crea al ejecutar una búsqueda en «Portales». Aquí se verá su estado,
                        cuántos anuncios entraron y cuántos cayeron en cuarentena.
                      </Vacio>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {sel && (
          <div className="space-y-4">
            {selVivo?.error_mensaje && (
              <Card titulo={`Job ${String(selVivo.id).slice(0, 8)} · fallido`}>
                <PanelFallo error={selVivo.error_mensaje} />
              </Card>
            )}

            <Card
              titulo="Modo manual · prompt para OpenClaw"
              acciones={<Boton variante="secundario" onClick={() => navigator.clipboard.writeText(prompt)}>Copiar</Boton>}
            >
              {/* `text-fg` explícito: el prompt es para leerlo y copiarlo, no un
                  dato secundario. Antes heredaba un gris de bajo contraste que lo
                  dejaba prácticamente ilegible sobre el fondo oscuro. */}
              <textarea
                readOnly
                value={prompt}
                spellCheck={false}
                className="campo w-full h-48 font-mono !text-xs leading-relaxed text-fg resize-y"
              />
            </Card>

            <Card titulo="Pegar JSON de vuelta">
              <textarea
                value={pegado}
                onChange={(e) => setPegado(e.target.value)}
                placeholder="Pega aquí el JSON que devuelve OpenClaw"
                spellCheck={false}
                className="campo w-full h-48 font-mono !text-xs leading-relaxed text-fg resize-y"
              />
              <div className="mt-3 flex flex-col sm:flex-row sm:items-center gap-3">
                <Boton cargando={ingestando} onClick={enviarManual}>
                  {ingestando ? "Ingestando" : "Ingestar resultado"}
                </Boton>
                {msg && (
                  <div className="flex-1 min-w-0">
                    <Aviso tono={msgTono} alCerrar={() => setMsg("")}>{msg}</Aviso>
                  </div>
                )}
              </div>
            </Card>

            {cuarentena.length > 0 && (
              <Card titulo={`Cuarentena (${cuarentena.length})`} subtitulo="anuncios que no validaron">
                <ul className="space-y-2.5">
                  {cuarentena.map((c) => (
                    <li key={c.id} className="border-b border-line/70 last:border-0 pb-2 last:pb-0">
                      <div className="text-[13px] text-fg truncate">{c.url_anuncio || "(sin url)"}</div>
                      <div className="text-xs text-danger cifra mt-0.5">{JSON.stringify(c.errores_validacion).slice(0, 200)}</div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
