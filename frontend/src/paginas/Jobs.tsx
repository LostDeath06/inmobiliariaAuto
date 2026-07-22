import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Boton, Card, Chip, Vacio } from "../ui";

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

export default function Jobs() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  const [prompt, setPrompt] = useState("");
  const [pegado, setPegado] = useState("");
  const [cuarentena, setCuarentena] = useState<any[]>([]);
  const [noReconocidas, setNoReconocidas] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

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
    try {
      const sobre = JSON.parse(pegado);
      const r = await api.post(`/api/jobs/${sel.id}/resultado-manual`, sobre);
      setMsg(`Ingesta: ${r.validos} válidos, ${r.cuarentena} en cuarentena, ${r.procesados} procesados.`);
      cargar(); abrir(sel);
    } catch (e) { setMsg(`Error: ${e}`); }
  };

  return (
    <div className="space-y-4">
      {noReconocidas.length > 0 && (
        <Card
          titulo="Señales fuera de catálogo"
          subtitulo="Claude devolvió códigos que el catálogo del país no contempla — revísalos"
        >
          <div className="space-y-2">
            {noReconocidas.map((n) => (
              <div key={n.inmueble_id} className="flex items-center justify-between gap-4 py-1.5 border-b border-line/70 last:border-0">
                <Link to={`/inmueble/${n.inmueble_id}`} className="text-fg hover:text-accent transition truncate">
                  {n.titulo || "(sin título)"}
                  <span className="text-faint text-xs ml-2">{[n.ciudad, n.pais].filter(Boolean).join(" · ")}</span>
                </Link>
                <div className="flex flex-wrap gap-1.5 justify-end shrink-0">
                  {(n.senales_no_reconocidas || []).map((c: string) => <Chip key={c} tono="warning">{c}</Chip>)}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <Card titulo="Jobs" subtitulo="auto-refresco cada 5 s">
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>Estado</th>
                  <th className="text-right">Válidos</th>
                  <th className="text-right">Cuar.</th>
                  <th className="text-right">Coste USD</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td><EstadoJob estado={j.estado} /></td>
                    <td className="text-right cifra text-fg">{j.total_anuncios_validos ?? "—"}</td>
                    <td className="text-right cifra text-muted">{j.total_anuncios_cuarentena ?? "—"}</td>
                    <td className="text-right cifra text-muted">{j.coste_estimado_usd ? Number(j.coste_estimado_usd).toFixed(4) : "—"}</td>
                    <td className="text-right"><Boton variante="fantasma" onClick={() => abrir(j)}>Abrir</Boton></td>
                  </tr>
                ))}
                {jobs.length === 0 && <tr><td colSpan={5}><Vacio>Sin jobs todavía</Vacio></td></tr>}
              </tbody>
            </table>
          </div>
        </Card>

        {sel && (
          <div className="space-y-4">
            <Card
              titulo="Modo manual · prompt para OpenClaw"
              acciones={<Boton variante="secundario" onClick={() => navigator.clipboard.writeText(prompt)}>Copiar</Boton>}
            >
              <textarea readOnly value={prompt} className="campo w-full h-40 font-mono text-xs resize-none" />
            </Card>

            <Card titulo="Pegar JSON de vuelta">
              <textarea
                value={pegado}
                onChange={(e) => setPegado(e.target.value)}
                placeholder="Pega aquí el JSON que devuelve OpenClaw"
                className="campo w-full h-40 font-mono text-xs resize-none"
              />
              <div className="mt-3 flex items-center gap-3">
                <Boton onClick={enviarManual}>Ingestar resultado</Boton>
                {msg && <span className="text-sm text-muted">{msg}</span>}
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
