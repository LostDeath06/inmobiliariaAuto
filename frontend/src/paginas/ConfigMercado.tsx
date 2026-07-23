import { useEffect, useState } from "react";
import { api, PAISES } from "../api";
import { Aviso, Boton, Card, Esqueleto, Vacio } from "../ui";

/** Marca visualmente los campos vacíos: sin estos datos el score es incompleto. */
function celdaVacia(v: any) {
  return v === null || v === undefined || v === "";
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
                        defaultValue={c.coste_m2 ?? ""} placeholder="vacío"
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
          <div className="tabla-scroll">
            <table>
              <thead><tr><th>Concepto</th><th>Tipo</th><th className="text-right">Valor</th><th>Moneda</th></tr></thead>
              <tbody>
                {gastos.map((g) => (
                  <tr key={g.id} className={celdaVacia(g.valor) ? "bg-warning/5" : ""}>
                    <td className="text-fg">{g.concepto}</td>
                    <td className="text-muted">{g.tipo}</td>
                    <td className={`text-right cifra ${celdaVacia(g.valor) ? "text-warning" : "text-fg"}`}>{g.valor ?? "vacío"}</td>
                    <td className="text-muted">{g.moneda || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
                    <td className={`text-right cifra ${celdaVacia(b.precio_m2_venta_medio) ? "text-warning" : "text-fg"}`}>{b.precio_m2_venta_medio ?? "vacío"}</td>
                    <td className={`text-right cifra ${celdaVacia(b.precio_m2_alquiler_medio) ? "text-warning" : "text-fg"}`}>{b.precio_m2_alquiler_medio ?? "vacío"}</td>
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
