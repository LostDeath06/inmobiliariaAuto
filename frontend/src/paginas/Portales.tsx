import { useEffect, useState } from "react";
import { api, PAISES } from "../api";
import { Boton, Card, Vacio, fmtDinero } from "../ui";

export default function Portales() {
  const [portales, setPortales] = useState<any[]>([]);
  const [busquedas, setBusquedas] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [np, setNp] = useState({ nombre: "", url_raiz: "", pais: "ES" });
  const [nb, setNb] = useState({ portal_id: "", ciudad: "", presupuesto_max: "", moneda: "EUR", tipo_inmueble: "", frecuencia_cron: "" });

  const cargar = () => {
    api.get("/api/portales").then(setPortales).catch(() => {});
    api.get("/api/busquedas").then(setBusquedas).catch(() => {});
  };
  useEffect(() => { cargar(); }, []);

  const crearPortal = async () => {
    await api.post("/api/portales", np);
    setMsg("Portal creado."); setNp({ nombre: "", url_raiz: "", pais: "ES" }); cargar();
  };
  const crearBusqueda = async () => {
    await api.post("/api/busquedas", {
      ...nb, presupuesto_max: nb.presupuesto_max ? Number(nb.presupuesto_max) : null,
      frecuencia_cron: nb.frecuencia_cron || null,
    });
    setMsg("Búsqueda creada."); cargar();
  };
  const ejecutar = async (id: string) => {
    const r = await api.post(`/api/busquedas/${id}/ejecutar`);
    setMsg(`Job ${r.job_id} · modo ${r.modo} · ${r.estado}`); cargar();
  };

  return (
    <div className="space-y-4">
      {msg && <div className="text-[13px] text-positive bg-positive/10 border border-positive/30 rounded-md px-3 py-2">{msg}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        <Card titulo="Nuevo portal">
          <div className="space-y-2.5">
            <div>
              <label className="etiqueta">Nombre</label>
              <input value={np.nombre} onChange={(e) => setNp({ ...np, nombre: e.target.value })} className="campo w-full" />
            </div>
            <div>
              <label className="etiqueta">URL raíz</label>
              <input value={np.url_raiz} onChange={(e) => setNp({ ...np, url_raiz: e.target.value })} className="campo w-full" />
            </div>
            <div>
              <label className="etiqueta">País</label>
              <select value={np.pais} onChange={(e) => setNp({ ...np, pais: e.target.value })} className="campo">
                {PAISES.map((p) => <option key={p}>{p}</option>)}
              </select>
            </div>
            <Boton onClick={crearPortal}>Crear portal</Boton>
          </div>
        </Card>

        <Card titulo="Nueva búsqueda">
          <div className="space-y-2.5">
            <div>
              <label className="etiqueta">Portal</label>
              <select value={nb.portal_id} onChange={(e) => setNb({ ...nb, portal_id: e.target.value })} className="campo w-full">
                <option value="">— portal —</option>
                {portales.map((p) => <option key={p.id} value={p.id}>{p.nombre} ({p.pais})</option>)}
              </select>
            </div>
            <div>
              <label className="etiqueta">Ciudad</label>
              <input value={nb.ciudad} onChange={(e) => setNb({ ...nb, ciudad: e.target.value })} className="campo w-full" />
            </div>
            <div className="flex gap-2">
              <div>
                <label className="etiqueta">Presupuesto máx.</label>
                <input value={nb.presupuesto_max} onChange={(e) => setNb({ ...nb, presupuesto_max: e.target.value })} className="campo w-36 cifra" />
              </div>
              <div>
                <label className="etiqueta">Moneda</label>
                <input value={nb.moneda} onChange={(e) => setNb({ ...nb, moneda: e.target.value })} className="campo w-20" />
              </div>
            </div>
            <div>
              <label className="etiqueta">Tipo</label>
              <input placeholder="PISO, CASA…" value={nb.tipo_inmueble} onChange={(e) => setNb({ ...nb, tipo_inmueble: e.target.value })} className="campo w-full" />
            </div>
            <div>
              <label className="etiqueta">Cron (opcional)</label>
              <input placeholder="0 8 * * *" value={nb.frecuencia_cron} onChange={(e) => setNb({ ...nb, frecuencia_cron: e.target.value })} className="campo w-full cifra" />
            </div>
            <Boton onClick={crearBusqueda}>Crear búsqueda</Boton>
          </div>
        </Card>
      </div>

      <Card titulo="Búsquedas">
        <div className="tabla-scroll">
          <table>
            <thead>
              <tr>
                <th>Ciudad</th>
                <th className="text-right">Presupuesto</th>
                <th>Tipo</th>
                <th>Cron</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {busquedas.map((b) => (
                <tr key={b.id}>
                  <td className="text-fg">{b.ciudad || "—"}</td>
                  <td className="text-right cifra text-fg">{b.presupuesto_max ? fmtDinero(b.presupuesto_max, b.moneda) : "—"}</td>
                  <td className="text-muted">{b.tipo_inmueble || "—"}</td>
                  <td className="cifra text-muted text-xs">{b.frecuencia_cron || "manual"}</td>
                  <td className="text-right"><Boton variante="secundario" onClick={() => ejecutar(b.id)}>Ejecutar ahora</Boton></td>
                </tr>
              ))}
              {busquedas.length === 0 && <tr><td colSpan={5}><Vacio>Sin búsquedas configuradas</Vacio></td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
