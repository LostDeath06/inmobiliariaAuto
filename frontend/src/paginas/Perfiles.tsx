import { useEffect, useState } from "react";
import { api } from "../api";
import { Aviso, Boton, Card, Esqueleto } from "../ui";

export default function Perfiles() {
  const [perfiles, setPerfiles] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  const [pesos, setPesos] = useState<Record<string, number>>({});
  const [supuestos, setSupuestos] = useState<Record<string, number>>({});
  const [aviso, setAviso] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [recalculando, setRecalculando] = useState(false);

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
    setGuardando(true);
    try {
      const r = await api.put(`/api/perfiles/${sel.id}`, { pesos, supuestos });
      setAviso(`Guardado. ${r.scores_marcados_obsoletos} scores marcados obsoletos: recalcula para verlos.`);
      cargar();
    } finally {
      setGuardando(false);
    }
  };

  const recalcular = async () => {
    setRecalculando(true);
    try {
      await api.post(`/api/pipeline/recalcular-todo?perfil_id=${sel.id}`);
      setAviso("Recálculo lanzado.");
    } finally {
      setRecalculando(false);
    }
  };

  if (!sel) return <EsqueletoPerfiles />;

  return (
    <div className="space-y-4">
      {/* Pestañas de perfil: deslizables en móvil, sin romper el ancho */}
      <div className="flex gap-1.5 overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0 pb-1">
        {perfiles.map((p) => (
          <button
            key={p.id}
            onClick={() => elegir(p)}
            className={`shrink-0 px-3 py-1.5 tactil:py-0 tactil:min-h-[44px] rounded-md text-[13px] tactil:text-sm font-medium
              transition-[background-color,color,border-color,box-shadow] duration-150 ${
              sel.id === p.id
                ? "bg-elevated text-fg border border-line shadow-elev-1"
                : "text-muted hover:text-fg hover:bg-elevated/60"
            }`}
          >
            {p.nombre}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        <Card titulo="Pesos del score" subtitulo="deben sumar 100%">
          {/* Móvil: etiqueta y valor arriba, slider a ancho completo debajo (dedo).
              Escritorio: la fila compacta de siempre. */}
          <div className="space-y-4 md:space-y-3">
            {Object.keys(pesos).map((k) => (
              <div key={k} className="md:flex md:items-center md:gap-3">
                <div className="flex items-center justify-between md:block md:w-44">
                  <label className="text-sm md:text-[13px] text-muted md:truncate md:block">{k}</label>
                  <span className="cifra text-sm text-fg md:hidden">{(pesos[k] * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range" min={0} max={1} step={0.05} value={pesos[k]}
                  onChange={(e) => setPesos({ ...pesos, [k]: Number(e.target.value) })}
                  className="w-full md:flex-1"
                  aria-label={k}
                />
                <span className="hidden md:block w-12 text-right cifra text-sm text-fg">{(pesos[k] * 100).toFixed(0)}%</span>
              </div>
            ))}
            {/* La suma cambia de color en cuanto deja de cuadrar: no hay que buscar
                el error, se ve mientras se arrastra el slider. */}
            <div
              className={`text-[13px] font-medium pt-1 transition-colors duration-200 ${
                sumaOk ? "text-positive" : "text-danger"
              }`}
            >
              Suma: <span className="cifra">{(suma * 100).toFixed(0)}%</span>{sumaOk ? "" : " · debe ser 100%"}
            </div>
          </div>
        </Card>

        <Card titulo="Supuestos financieros del inversor">
          <div className="space-y-2.5">
            {Object.keys(supuestos).map((k) => (
              <div key={k} className="flex items-center justify-between gap-3">
                <label className="text-sm md:text-[13px] text-muted md:w-44 md:truncate">{k}</label>
                <input
                  type="number" step="any" value={supuestos[k]}
                  onChange={(e) => setSupuestos({ ...supuestos, [k]: Number(e.target.value) })}
                  className="campo w-28 md:w-32 cifra text-right"
                  aria-label={k}
                />
              </div>
            ))}
          </div>
        </Card>
      </div>

      {aviso && <Aviso tono="warning" alCerrar={() => setAviso("")}>{aviso}</Aviso>}

      <div className="flex flex-col sm:flex-row gap-2">
        <Boton className="w-full sm:w-auto" cargando={guardando} onClick={guardar}>
          {guardando ? "Guardando" : "Guardar"}
        </Boton>
        <Boton className="w-full sm:w-auto" variante="secundario" cargando={recalculando} onClick={recalcular}>
          {recalculando ? "Recalculando" : "Recalcular scores del perfil"}
        </Boton>
      </div>
    </div>
  );
}

function EsqueletoPerfiles() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Cargando perfiles">
      <div className="flex gap-1.5">
        <Esqueleto className="h-9 w-44" />
        <Esqueleto className="h-9 w-44" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[0, 1].map((i) => (
          <div key={i} className="rounded-lg border border-line bg-surface shadow-elev-1 overflow-hidden">
            <div className="h-11 border-b border-line flex items-center px-4">
              <Esqueleto className="h-3.5 w-32" />
            </div>
            <div className="p-4 space-y-4">
              {[0, 1, 2, 3, 4, 5, 6].map((j) => (
                <div key={j} className="flex items-center gap-3">
                  <Esqueleto className="h-3.5 w-40 shrink-0" />
                  <Esqueleto className="h-1.5 flex-1" />
                  <Esqueleto className="h-3.5 w-9 shrink-0" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
