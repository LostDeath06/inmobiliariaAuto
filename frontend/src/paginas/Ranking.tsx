import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, PAISES } from "../api";
import { AvisoProvisional, BadgeCalidad, BadgeDup, BadgeSenalIgnorada, BadgeTuristica, Card, Interruptor, ScoreCelda, Vacio, fmtDinero, fmtNum } from "../ui";

export default function Ranking() {
  const [perfiles, setPerfiles] = useState<any[]>([]);
  const [perfilId, setPerfilId] = useState("");
  const [pais, setPais] = useState("");
  const [sinRiesgoPais, setSinRiesgoPais] = useState(false);
  const [filas, setFilas] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/perfiles").then((p) => {
      setPerfiles(p);
      const pred = p.find((x: any) => x.es_predeterminado) || p[0];
      if (pred) setPerfilId(pred.id);
    }).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!perfilId) return;
    const q = new URLSearchParams({ perfil_id: perfilId, sin_riesgo_pais: String(sinRiesgoPais), limit: "200" });
    if (pais) q.set("pais", pais);
    setError("");
    api.get(`/api/ranking?${q}`).then(setFilas).catch((e) => setError(String(e)));
  }, [perfilId, pais, sinRiesgoPais]);

  return (
    <div className="space-y-5">
      <div className="flex items-end gap-5 flex-wrap">
        <div>
          <label className="etiqueta">Perfil de inversor</label>
          <select value={perfilId} onChange={(e) => setPerfilId(e.target.value)} className="campo min-w-[200px]">
            {perfiles.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
        </div>
        <div>
          <label className="etiqueta">País</label>
          <select value={pais} onChange={(e) => setPais(e.target.value)} className="campo">
            <option value="">Global</option>
            {PAISES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div className="pb-2">
          <Interruptor
            activo={sinRiesgoPais}
            onCambiar={setSinRiesgoPais}
            etiqueta="Sin riesgo país (score bruto)"
            title="Ver scores brutos, sin el multiplicador de riesgo país"
          />
        </div>
      </div>

      {error && <div className="text-sm text-danger bg-danger/10 border border-danger/30 rounded-md px-3 py-2">{error}</div>}

      <Card
        titulo="Ranking"
        subtitulo={`${filas.length} inmuebles · ordenado por ${sinRiesgoPais ? "score bruto" : "score total"}`}
      >
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th className="w-10 text-right">#</th>
                <th className="text-right w-32">Score</th>
                <th>Inmueble</th>
                <th className="text-right">Precio</th>
                <th className="text-right">m²</th>
                <th>Calidad</th>
                <th className="text-right">Marcas</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f, i) => {
                const superficie = f.superficie_util_m2 || f.superficie_construida_m2;
                const score = sinRiesgoPais ? f.score_bruto : f.score_total;
                return (
                  <tr key={f.inmueble_id}>
                    <td className="text-right cifra text-faint text-xs">{i + 1}</td>
                    <td className="text-right"><ScoreCelda valor={score} /></td>
                    <td className="max-w-sm">
                      <Link className="text-fg hover:text-accent transition truncate block" to={`/inmueble/${f.inmueble_id}`}>
                        {f.titulo || "(sin título)"}
                      </Link>
                      <span className="text-xs text-faint">{[f.ciudad, f.pais].filter(Boolean).join(" · ") || "—"}</span>
                    </td>
                    <td className="text-right cifra text-fg whitespace-nowrap">{fmtDinero(f.precio, f.moneda)}</td>
                    <td className="text-right cifra text-muted">{superficie ? fmtNum(superficie) : "—"}</td>
                    <td><BadgeCalidad estado={f.estado_calidad} /></td>
                    <td>
                      <div className="flex items-center gap-1.5 justify-end flex-wrap">
                        {f.perfil_zona === "TURISTICA" && <BadgeTuristica />}
                        {f.desglose?.senales_no_reconocidas?.length > 0 && (
                          <BadgeSenalIgnorada pais={f.pais} />
                        )}
                        {f.usa_parametros_provisionales && <AvisoProvisional />}
                        {f.posible_duplicado_cross_portal && <BadgeDup />}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {filas.length === 0 && !error && (
                <tr>
                  <td colSpan={7}>
                    <Vacio>Sin inmuebles en el ranking. ¿País configurado y con datos cargados?</Vacio>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
