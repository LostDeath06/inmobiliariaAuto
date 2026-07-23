import { useEffect, useState } from "react";
import { api, PAISES } from "../api";
import { Aviso, Boton, Card, Esqueleto, Vacio, fmtCantidad, fmtDinero, fmtPorcentaje } from "../ui";

/** Marca visualmente los campos vacíos: sin estos datos el score es incompleto. */
function celdaVacia(v: any) {
  return v === null || v === undefined || v === "";
}

/** Valor de un gasto ya formateado con su unidad: PORCENTAJE → "7 %", FIJO → "400 EUR". */
function valorGasto(g: any): string | null {
  if (celdaVacia(g.valor)) return null;
  return g.tipo === "PORCENTAJE" ? fmtPorcentaje(g.valor) : fmtDinero(g.valor, g.moneda);
}

/** Número sin ceros de cola para un input editable: "220.000000" → "220". */
function numLimpio(v: any): string {
  if (celdaVacia(v)) return "";
  const n = Number(v);
  return Number.isNaN(n) ? String(v) : String(n);
}

function Chevron() {
  // La rotación va en el <span>, no en el <svg>: los SVG tienen atributo
  // `transform` de presentación que compite con el CSS y algunos navegadores lo
  // resuelven mal. Rotar un span es equivalente y funciona en todos.
  return (
    <span className="chevron inline-flex shrink-0 text-faint" aria-hidden>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="m9 6 6 6-6 6" />
      </svg>
    </span>
  );
}

export default function ConfigMercado() {
  const [pais, setPais] = useState("ES");
  const [costes, setCostes] = useState<any[]>([]);
  const [gastos, setGastos] = useState<any[]>([]);
  const [benchmarks, setBenchmarks] = useState<any[]>([]);
  const [cargando, setCargando] = useState(true);
  const [tasa, setTasa] = useState({ moneda_origen: "USD", moneda_destino: "EUR", tasa: "", fecha: "" });
  const [guardandoTasa, setGuardandoTasa] = useState(false);
  // Id de la fila recién guardada: su campo parpadea en verde un instante. Sin
  // eso, escribir y salir del campo no da ninguna señal de que se haya guardado.
  const [recienGuardado, setRecienGuardado] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  const cargar = () => {
    setCargando(true);
    Promise.all([
      api.get(`/api/config/costes-reforma?pais=${pais}`).then(setCostes),
      api.get(`/api/config/gastos-adquisicion?pais=${pais}`).then(setGastos),
      api.get(`/api/config/benchmarks?pais=${pais}`).then(setBenchmarks),
    ]).finally(() => setCargando(false));
  };
  useEffect(() => { cargar(); }, [pais]);

  useEffect(() => {
    if (!recienGuardado) return;
    const t = setTimeout(() => setRecienGuardado(null), 1200);
    return () => clearTimeout(t);
  }, [recienGuardado]);

  const guardarCoste = async (c: any, valor: string) => {
    await api.put("/api/config/costes-reforma", {
      pais, nivel_reforma: c.nivel_reforma, coste_m2: valor === "" ? null : Number(valor), moneda: c.moneda,
    });
    setRecienGuardado(c.id);
    setMsg("Coste guardado.");
    cargar();
  };

  const guardarTasa = async () => {
    setGuardandoTasa(true);
    try {
      await api.put("/api/config/tipos-cambio", { ...tasa, tasa: Number(tasa.tasa) });
      setMsg("Tipo de cambio cargado.");
    } finally {
      setGuardandoTasa(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <label className="etiqueta mb-0">País</label>
        <select value={pais} onChange={(e) => setPais(e.target.value)} className="campo">
          {PAISES.map((p) => <option key={p}>{p}</option>)}
        </select>
      </div>

      {msg && <Aviso alCerrar={() => setMsg("")}>{msg}</Aviso>}

      <Card titulo={`Costes de reforma · ${pais}`} subtitulo="€/m² por nivel de reforma">
        {cargando ? (
          <EsqueletoTabla filas={3} />
        ) : costes.length === 0 ? (
          <Vacio titulo="Sin costes de reforma cargados">
            Sin €/m² por nivel, el componente <span className="cifra">margen_reforma</span> no se puede calcular
            y el score de este país sale PARCIAL.
          </Vacio>
        ) : (
          <div className="tabla-scroll">
            <table>
              <thead><tr><th>Nivel</th><th className="text-right">Coste/m²</th><th>Moneda</th></tr></thead>
              <tbody>
                {costes.map((c) => (
                  <tr key={c.id} className={celdaVacia(c.coste_m2) ? "bg-warning/5" : ""}>
                    <td className="text-fg">{c.nivel_reforma}</td>
                    <td className="text-right">
                      <input
                        defaultValue={numLimpio(c.coste_m2)} placeholder="vacío"
                        onBlur={(e) => guardarCoste(c, e.target.value)}
                        className={`campo w-28 text-right cifra ${
                          recienGuardado === c.id
                            ? "border-positive ring-2 ring-positive/25"
                            : celdaVacia(c.coste_m2) ? "border-warning/50" : ""
                        }`}
                      />
                    </td>
                    <td className="text-muted">{c.moneda || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card titulo={`Gastos de adquisición · ${pais}`} subtitulo="filas vacías → el inmueble sale NO_CALCULABLE">
        {cargando ? (
          <EsqueletoTabla filas={4} />
        ) : gastos.length === 0 ? (
          <Vacio titulo="Sin conceptos configurados">
            Añade los gastos de compra del país (ITP, notaría, registro, gestoría). Sin ellos no hay coste
            total de adquisición, y sin coste total no hay ROI.
          </Vacio>
        ) : (
          <GastosAdquisicion gastos={gastos} />
        )}
      </Card>

      <Card titulo={`Benchmarks de zona · ${pais}`}>
        {cargando ? (
          <EsqueletoTabla filas={4} />
        ) : benchmarks.length === 0 ? (
          <Vacio titulo="Sin benchmarks de zona cargados">
            Sin €/m² de referencia no hay <span className="cifra">descuento_mercado</span> ni{" "}
            <span className="cifra">calidad_zona</span>: dos de los siete componentes del score se quedan fuera
            y su peso se reparte entre el resto.
          </Vacio>
        ) : (
          <div className="tabla-scroll">
            <table>
              <thead><tr><th>Ciudad</th><th>Barrio</th><th className="text-right">€/m² venta</th><th className="text-right">€/m² alquiler</th></tr></thead>
              <tbody>
                {benchmarks.map((b) => (
                  <tr key={b.id}>
                    <td className="text-fg">{b.ciudad}</td>
                    <td className="text-muted">{b.barrio || "—"}</td>
                    <td className={`text-right cifra ${celdaVacia(b.precio_m2_venta_medio) ? "text-warning" : "text-fg"}`}>{celdaVacia(b.precio_m2_venta_medio) ? "vacío" : fmtCantidad(b.precio_m2_venta_medio)}</td>
                    <td className={`text-right cifra ${celdaVacia(b.precio_m2_alquiler_medio) ? "text-warning" : "text-fg"}`}>{celdaVacia(b.precio_m2_alquiler_medio) ? "vacío" : fmtCantidad(b.precio_m2_alquiler_medio)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card titulo="Tipos de cambio" subtitulo="carga manual, sin feeds">
        <div className="flex items-end gap-2 flex-wrap">
          <Campo l="Origen" v={tasa.moneda_origen} on={(v) => setTasa({ ...tasa, moneda_origen: v })} />
          <Campo l="Destino" v={tasa.moneda_destino} on={(v) => setTasa({ ...tasa, moneda_destino: v })} />
          <Campo l="Tasa" v={tasa.tasa} on={(v) => setTasa({ ...tasa, tasa: v })} />
          <Campo l="Fecha" v={tasa.fecha} on={(v) => setTasa({ ...tasa, fecha: v })} ph="YYYY-MM-DD" />
          <Boton cargando={guardandoTasa} onClick={guardarTasa}>
            {guardandoTasa ? "Cargando" : "Cargar tasa"}
          </Boton>
        </div>
      </Card>
    </div>
  );
}

/** Gastos de adquisición, presentados para que se lean.
 *
 *  El problema: cargado el ITP español, había 19 filas idénticas «ITP» sin decir a
 *  qué comunidad pertenecía cada una (la columna `region` existía en BD pero la
 *  tabla no la mostraba). Ilegible y con scroll para rato.
 *
 *  La estructura: los gastos COMUNES del país (region vacía: notaría, registro…)
 *  aparte, en una lista compacta; los REGIONALES agrupados por concepto en un
 *  desplegable colapsable — el ITP de las 19 comunidades cabe en un grupo, con su
 *  comunidad al lado del valor. Solo presentación: no toca datos ni lógica. */
function GastosAdquisicion({ gastos }: { gastos: any[] }) {
  const comunes = gastos.filter((g) => !g.region);
  const regionales = gastos.filter((g) => g.region);

  const grupos: Record<string, any[]> = {};
  for (const g of regionales) (grupos[g.concepto] ??= []).push(g);

  return (
    <div className="space-y-4">
      {comunes.length > 0 && (
        <div>
          <div className="etiqueta">Comunes · todo el país</div>
          <dl className="text-sm divide-y divide-line/70">
            {comunes.map((g) => {
              const v = valorGasto(g);
              return (
                <div key={g.id} className="flex items-baseline justify-between gap-4 py-1.5">
                  <dt className="text-fg min-w-0">
                    <span className="truncate">{g.concepto}</span>
                    {g.exento_confotur && (
                      <span className="ml-2 text-[10px] font-medium uppercase tracking-wide text-positive/80 whitespace-nowrap">
                        exento CONFOTUR
                      </span>
                    )}
                  </dt>
                  <dd className={`cifra shrink-0 ${v === null ? "text-warning" : "text-fg"}`}>{v ?? "vacío"}</dd>
                </div>
              );
            })}
          </dl>
        </div>
      )}

      {Object.entries(grupos).map(([concepto, filas]) => {
        // Ordena por valor: se lee de la comunidad más barata a la más cara.
        const ordenadas = [...filas].sort((a, b) => Number(a.valor) - Number(b.valor));
        const nums = filas.map((f) => Number(f.valor)).filter((n) => !Number.isNaN(n));
        const esPct = filas[0]?.tipo === "PORCENTAJE";
        const fmt = (v: number) => (esPct ? fmtPorcentaje(v) : fmtDinero(v, filas[0]?.moneda));
        const rango = nums.length
          ? Math.min(...nums) === Math.max(...nums)
            ? fmt(nums[0])
            : `${fmt(Math.min(...nums))} – ${fmt(Math.max(...nums))}`
          : "sin valores";
        const exento = filas.some((f) => f.exento_confotur);
        return (
          <details key={concepto} open>
            <summary className="flex items-center gap-2 py-1">
              <Chevron />
              <span className="text-sm font-medium text-fg">{concepto}</span>
              <span className="text-xs text-muted">
                · {filas.length} {filas.length === 1 ? "región" : "comunidades"} · {rango}
              </span>
              {exento && (
                <span className="text-[10px] font-medium uppercase tracking-wide text-positive/80">exento CONFOTUR</span>
              )}
            </summary>
            <div className="mt-1.5 ml-[20px] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-0.5">
              {ordenadas.map((g) => {
                const v = valorGasto(g);
                return (
                  <div key={g.id} className="flex items-baseline justify-between gap-3 border-b border-line/40 py-1">
                    <span className="text-sm text-muted truncate">{g.region}</span>
                    <span className={`cifra text-sm shrink-0 ${v === null ? "text-warning" : "text-fg"}`}>{v ?? "vacío"}</span>
                  </div>
                );
              })}
            </div>
          </details>
        );
      })}
    </div>
  );
}

function EsqueletoTabla({ filas }: { filas: number }) {
  return (
    <div className="space-y-px" aria-busy="true">
      <div className="flex gap-4 pb-2 border-b border-line">
        <Esqueleto className="h-2.5 w-16" />
        <Esqueleto className="h-2.5 w-20" />
        <Esqueleto className="h-2.5 w-14" />
      </div>
      {Array.from({ length: filas }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 h-[41px] border-b border-line/70">
          <Esqueleto className="h-3.5 w-28" />
          <Esqueleto className="h-3.5 w-20" />
          <Esqueleto className="h-3.5 w-12" />
        </div>
      ))}
    </div>
  );
}

function Campo({ l, v, on, ph }: { l: string; v: string; on: (v: string) => void; ph?: string }) {
  return (
    // En móvil cada campo ocupa media fila (dos por línea); en escritorio, ancho fijo.
    <div className="flex-1 min-w-[7.5rem] sm:flex-none">
      <label className="etiqueta">{l}</label>
      <input value={v} placeholder={ph} onChange={(e) => on(e.target.value)} className="campo w-full sm:w-28 cifra" />
    </div>
  );
}
