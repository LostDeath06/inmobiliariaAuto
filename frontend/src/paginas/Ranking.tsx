import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, PAISES } from "../api";
import {
  AvisoProvisional, BadgeCalidad, BadgeDup, BadgeSenalIgnorada, BadgeTuristica, Card,
  EsqueletoRanking, Interruptor, ScoreCelda, Vacio, fmtDinero, fmtNum, paso,
} from "../ui";

export default function Ranking() {
  const [perfiles, setPerfiles] = useState<any[]>([]);
  const [perfilId, setPerfilId] = useState("");
  const [pais, setPais] = useState("");
  const [sinRiesgoPais, setSinRiesgoPais] = useState(false);
  const [filas, setFilas] = useState<any[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/perfiles").then((p) => {
      setPerfiles(p);
      const pred = p.find((x: any) => x.es_predeterminado) || p[0];
      if (pred) setPerfilId(pred.id);
    }).catch((e) => { setError(String(e)); setCargando(false); });
  }, []);

  useEffect(() => {
    if (!perfilId) return;
    const q = new URLSearchParams({ perfil_id: perfilId, sin_riesgo_pais: String(sinRiesgoPais), limit: "200" });
    if (pais) q.set("pais", pais);
    setError("");
    setCargando(true);
    api.get(`/api/ranking?${q}`)
      .then(setFilas)
      .catch((e) => setError(String(e)))
      .finally(() => setCargando(false));
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

      {error && (
        <div className="aparecer text-sm text-danger bg-danger/10 border border-danger/30 rounded-md px-3 py-2 shadow-elev-1">
          {error}
        </div>
      )}

      <Card
        titulo="Ranking"
        subtitulo={
          cargando
            ? "cargando…"
            : `${filas.length} inmuebles · ordenado por ${sinRiesgoPais ? "score bruto" : "score total"}`
        }
      >
        {cargando ? (
          <EsqueletoRanking />
        ) : filas.length === 0 && !error ? (
          <Vacio titulo="Sin inmuebles en el ranking">
            {pais
              ? `No hay inmuebles puntuados en ${pais}. Comprueba en «Estado por país» que su configuración de mercado esté cargada, y en «Portales» que haya una búsqueda ejecutada.`
              : "No hay ningún inmueble puntuado todavía. Ejecuta una búsqueda en «Portales» o revisa «Estado por país» para ver qué configuración falta."}
          </Vacio>
        ) : (
          <>
            {/* ---------- MÓVIL Y TABLET (<1024px): tarjetas apiladas, sin scroll horizontal ----------
                 A 768px la tabla mide ~890px y obligaría a arrastrar de lado; por eso el corte
                 es lg y no md. ---------- */}
            <ul className="lg:hidden space-y-2 escalonado">
              {filas.map((f, i) => {
                const superficie = f.superficie_util_m2 || f.superficie_construida_m2;
                const score = sinRiesgoPais ? f.score_bruto : f.score_total;
                return (
                  <li
                    key={f.inmueble_id}
                    {...paso(i)}
                    className="relative rounded-lg border border-line bg-elevated/40 p-3 shadow-elev-1
                      transition-[box-shadow,border-color,background-color] duration-150
                      hover:shadow-elev-2 hover:border-muted/30 active:bg-elevated"
                  >
                    {/* La tarjeta entera lleva a la ficha, pero las marcas de arriba siguen
                        siendo consultables con el dedo (no navegan). */}
                    <Link
                      to={`/inmueble/${f.inmueble_id}`}
                      aria-label={f.titulo || "Ver ficha del inmueble"}
                      className="absolute inset-0 rounded-lg"
                    />

                    <div className="pointer-events-none">
                      {/* El score manda: cifra grande arriba a la derecha, el resto le cede sitio. */}
                      <div className="flex items-start justify-between gap-3">
                        <span className="cifra text-[11px] text-faint pt-1.5">#{i + 1}</span>
                        <ScoreCelda valor={score} tamano="lg" />
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
                        <span className="cifra text-faint text-sm whitespace-nowrap">
                          {superficie ? `${fmtNum(superficie)} m²` : "—"}
                        </span>
                      </div>
                    </div>

                    <div className="relative mt-2 flex items-center gap-1.5 flex-wrap">
                      <span className="pointer-events-none"><BadgeCalidad estado={f.estado_calidad} /></span>
                      {marcas(f)}
                    </div>
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
                    <th className="text-right w-36">Score</th>
                    <th>Inmueble</th>
                    <th className="text-right">Precio</th>
                    <th className="text-right">m²</th>
                    <th>Calidad</th>
                    <th className="text-right">Marcas</th>
                  </tr>
                </thead>
                <tbody className="escalonado">
                  {filas.map((f, i) => {
                    const superficie = f.superficie_util_m2 || f.superficie_construida_m2;
                    const score = sinRiesgoPais ? f.score_bruto : f.score_total;
                    return (
                      <tr key={f.inmueble_id} {...paso(i)} className="group">
                        <td className="text-right cifra text-faint text-xs">{i + 1}</td>
                        <td className="text-right py-1.5"><ScoreCelda valor={score} /></td>
                        <td className="max-w-sm">
                          <Link className="text-fg group-hover:text-accent transition-colors truncate block" to={`/inmueble/${f.inmueble_id}`}>
                            {f.titulo || "(sin título)"}
                          </Link>
                          <span className="text-xs text-faint">{[f.ciudad, f.pais].filter(Boolean).join(" · ") || "—"}</span>
                        </td>
                        <td className="text-right cifra text-fg whitespace-nowrap">{fmtDinero(f.precio, f.moneda)}</td>
                        <td className="text-right cifra text-faint">{superficie ? fmtNum(superficie) : "—"}</td>
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
