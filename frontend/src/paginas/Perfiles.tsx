import { useEffect, useState } from "react";
import { api } from "../api";
import { Boton, Card, Vacio } from "../ui";

export default function Perfiles() {
  const [perfiles, setPerfiles] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  const [pesos, setPesos] = useState<Record<string, number>>({});
  const [supuestos, setSupuestos] = useState<Record<string, number>>({});
  const [aviso, setAviso] = useState("");

  const cargar = () => api.get("/api/perfiles").then((p) => {
    setPerfiles(p);
    if (p[0]) elegir(p[0]);
  });
  useEffect(() => { cargar(); }, []);

  const elegir = (p: any) => {
    setSel(p);
    setPesos({ ...p.pesos });
    setSupuestos({ ...p.supuestos });
    setAviso("");
  };

  const suma = Object.values(pesos).reduce((a, b) => a + Number(b || 0), 0);
  const sumaOk = Math.abs(suma - 1) < 0.001;

  const guardar = async () => {
    const r = await api.put(`/api/perfiles/${sel.id}`, { pesos, supuestos });
    setAviso(`Guardado. ${r.scores_marcados_obsoletos} scores marcados obsoletos: recalcula para verlos.`);
    cargar();
  };

  const recalcular = async () => {
    await api.post(`/api/pipeline/recalcular-todo?perfil_id=${sel.id}`);
    setAviso("Recálculo lanzado.");
  };

  if (!sel) return <Vacio>Cargando…</Vacio>;

  return (
    <div className="space-y-4">
      <div className="flex gap-1.5">
        {perfiles.map((p) => (
          <button
            key={p.id}
            onClick={() => elegir(p)}
            className={`px-3 py-1.5 rounded-md text-[13px] font-medium transition ${
              sel.id === p.id ? "bg-elevated text-fg border border-line" : "text-muted hover:text-fg hover:bg-elevated/60"
            }`}
          >
            {p.nombre}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        <Card titulo="Pesos del score" subtitulo="deben sumar 100%">
          <div className="space-y-3">
            {Object.keys(pesos).map((k) => (
              <div key={k} className="flex items-center gap-3">
                <label className="w-44 text-[13px] text-muted truncate">{k}</label>
                <input
                  type="range" min={0} max={1} step={0.05} value={pesos[k]}
                  onChange={(e) => setPesos({ ...pesos, [k]: Number(e.target.value) })}
                  className="flex-1 accent-accent"
                />
                <span className="w-12 text-right cifra text-sm text-fg">{(pesos[k] * 100).toFixed(0)}%</span>
              </div>
            ))}
            <div className={`text-[13px] font-medium pt-1 ${sumaOk ? "text-positive" : "text-danger"}`}>
              Suma: <span className="cifra">{(suma * 100).toFixed(0)}%</span>{sumaOk ? "" : " · debe ser 100%"}
            </div>
          </div>
        </Card>

        <Card titulo="Supuestos financieros del inversor">
          <div className="space-y-2.5">
            {Object.keys(supuestos).map((k) => (
              <div key={k} className="flex items-center gap-3">
                <label className="w-44 text-[13px] text-muted truncate">{k}</label>
                <input
                  type="number" step="any" value={supuestos[k]}
                  onChange={(e) => setSupuestos({ ...supuestos, [k]: Number(e.target.value) })}
                  className="campo w-32 cifra"
                />
              </div>
            ))}
          </div>
        </Card>
      </div>

      {aviso && <div className="text-[13px] text-warning bg-warning/10 border border-warning/30 rounded-md px-3 py-2">{aviso}</div>}

      <div className="flex gap-2">
        <Boton onClick={guardar}>Guardar</Boton>
        <Boton variante="secundario" onClick={recalcular}>Recalcular scores del perfil</Boton>
      </div>
    </div>
  );
}
