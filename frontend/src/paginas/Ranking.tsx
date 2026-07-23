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

  /** Marcas de la fila. Se reutilizan en tabla y tarjeta para no divergir. */
  const marcas = (f: any) => (
    <>
      {f.perfil_zona === "TURISTICA" && <BadgeTuristica />}
      {f.desglose?.senales_no_reconocidas?.length > 0 && <BadgeSenalIgnorada pais={f.pais} />}
      {f.usa_parametros_provisionales && <AvisoProvisional />}
      {f.posible_duplicado_cross_portal && <BadgeDup />}
    </>
  );

  return (
    <div className="space-y-4 md:space-y-5">
      {/* Filtros: en columna en móvil (selects a ancho completo), en fila en escritorio */}
      <div className="flex flex-col sm:flex-row sm:items-end gap-3 sm:gap-5 sm:flex-wrap">
        <div className="sm:min-w-[200px]">
          <label className="etiqueta">Perfil de inversor</label>
          <select value={perfilId} onChange={(e) => setPerfilId(e.target.value)} className="campo w-full sm:min-w-[200px]">
            {perfiles.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
        </div>
        <div>
          <label className="etiqueta">País</label>
          <select value={pais} onChange={(e) => setPais(e.target.value)} className="campo w-full sm:w-auto">
            <option value="">Global</option>
            {PAISES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div className="sm:pb-2 py-1">
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
        {filas.length === 0 && !error ? (
          <Vacio>Sin inmuebles en el ranking. ¿País configurado y con datos cargados?</Vacio>
        ) : (
          <>
            {/* ---------- MÓVIL Y TABLET (<1024px): tarjetas apiladas, sin scroll horizontal ----------
                 A 768px la tabla mide ~890px y obligaría a arrastrar de lado; por eso el corte
                 es lg y no md. ---------- */}
            <ul className="lg:hidden space-y-2">
              {filas.map((f, i) => {
                const superficie = f.superficie_util_m2 || f.superficie_construida_m2;
                const score = sinRiesgoPais ? f.score_bruto : f.score_total;
                return (
                  <li key={f.inmueble_id}>
                    <Link
                      to={`/inmueble/${f.inmueble_id}`}
                      className="block rounded-lg border border-line bg-elevated/40 active:bg-elevated p-3 transition"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="cifra text-xs text-faint">#{i + 1}</span>
                        <ScoreCelda valor={score} />
                      </div>

                      <div className="mt-1.5 text-fg text-[15px] leading-snug line-clamp-2">
                        {f.titulo || "(sin título)"}
                      </div>
                      <div className="text-xs text-faint mt-0.5">
                        {[f.ciudad, f.pais].filter(Boolean).join(" · ") || "—"}
                      </div>

                      <div className="mt-2.5 flex items-center justify-between gap-3 border-t border-line/70 pt-2">
                        <span className="cifra text-fg text-sm whitespace-nowrap">
                          {fmtDinero(f.precio, f.moneda)}
                        </span>
                        <span className="cifra text-muted text-sm whitespace-nowrap">
                          {superficie ? `${fmtNum(superficie)} m²` : "—"}
                        </span>
                      </div>

                      <div className="mt-2 flex items-center gap-1.5 flex-wrap">
                        <BadgeCalidad estado={f.estado_calidad} />
                        {marcas(f)}
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>

            {/* ---------- ESCRITORIO (>=1024px): la tabla densa de siempre ---------- */}
            <div className="hidden lg:block overflow-x-auto">
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
                          <div className="flex items-center gap-1.5 justify-end flex-wrap">{marcas(f)}</div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
