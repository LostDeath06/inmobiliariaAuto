import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, PAISES } from "../api";
import {
  BadgeCalidad, BadgeConfotur, Card, Esqueleto, Vacio, fmtDinero, fmtNum, paso,
} from "../ui";

/** Todos los inmuebles cargados, puntúen o no.
 *
 *  El ranking excluye NO_CALCULABLE y DESCARTADO_RIESGO, y hace bien: un score sin
 *  configuración de mercado detrás no es un score. Pero eso dejaba inmuebles
 *  REALES fuera de todas las pantallas — entraban al sistema y desaparecían.
 *  Esta vista es el sitio donde siempre están, con su estado a la vista. */
export default function Inventario() {
  const [inmuebles, setInmuebles] = useState<any[]>([]);
  const [cargando, setCargando] = useState(true);
  const [pais, setPais] = useState("");
  const [estado, setEstado] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const q = new URLSearchParams({ limit: "500" });
    if (pais) q.set("pais", pais);
    setCargando(true);
    setError("");
    api.get(`/api/inmuebles?${q}`)
      .then(setInmuebles)
      .catch((e) => setError(String(e)))
      .finally(() => setCargando(false));
  }, [pais]);

  const filas = useMemo(
    () => (estado ? inmuebles.filter((i) => i.estado_calidad === estado) : inmuebles),
    [inmuebles, estado],
  );

  const conteos = useMemo(() => {
    const c: Record<string, number> = {};
    for (const i of inmuebles) {
      const e = i.estado_calidad || "SIN_ESTADO";
      c[e] = (c[e] || 0) + 1;
    }
    return c;
  }, [inmuebles]);

  const sinPuntuar = (conteos.NO_CALCULABLE || 0) + (conteos.DESCARTADO_RIESGO || 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-end gap-3 sm:gap-5 sm:flex-wrap">
        <div>
          <label className="etiqueta">País</label>
          <select value={pais} onChange={(e) => setPais(e.target.value)} className="campo w-full sm:w-auto">
            <option value="">Todos</option>
            {PAISES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className="etiqueta">Estado del dato</label>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} className="campo w-full sm:w-auto">
            <option value="">Todos</option>
            {["COMPLETO", "PARCIAL", "NO_CALCULABLE", "DESCARTADO_RIESGO"].map((e) => (
              <option key={e} value={e}>{e}{conteos[e] ? ` (${conteos[e]})` : ""}</option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="aparecer text-sm text-danger bg-danger/10 border border-danger/30 rounded-md px-3 py-2 shadow-elev-1">
          {error}
        </div>
      )}

      {!cargando && sinPuntuar > 0 && (
        <div className="aparecer rounded-lg border border-warning/40 bg-warning/10 px-3 py-2.5 text-[13px] text-muted leading-relaxed shadow-elev-1">
          <strong className="text-fg font-medium">{sinPuntuar}</strong> de {inmuebles.length} inmuebles
          no pueden puntuar todavía y por eso no salen en el ranking. No es un fallo: sin
          configuración de mercado del país, un score no significaría nada.{" "}
          <Link to="/estado" className="text-accent hover:underline">Ver qué falta por país</Link>.
        </div>
      )}

      <Card
        titulo="Inventario"
        subtitulo={cargando ? "cargando…" : `${filas.length} de ${inmuebles.length} inmuebles`}
      >
        {cargando ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 h-[41px] border-b border-line/70">
                <Esqueleto className="h-4 flex-1 max-w-sm" />
                <Esqueleto className="h-4 w-24" />
                <Esqueleto className="h-3 w-20" />
              </div>
            ))}
          </div>
        ) : filas.length === 0 ? (
          <Vacio variante="panel" titulo="Ningún inmueble con esos filtros">
            {inmuebles.length === 0
              ? "No hay inmuebles cargados. Ejecuta una búsqueda en «Portales» para que OpenClaw traiga anuncios."
              : "Prueba a quitar el filtro de estado: puede que los que hay estén en otro."}
          </Vacio>
        ) : (
          <>
            {/* Móvil y tablet: tarjetas, sin arrastrar de lado */}
            <ul className="lg:hidden space-y-2 escalonado">
              {filas.map((f, i) => (
                <li
                  key={f.id}
                  {...paso(i)}
                  className="relative rounded-lg border border-line bg-elevated/40 p-3 shadow-elev-1
                    transition-[box-shadow,border-color] duration-150 hover:shadow-elev-2 hover:border-muted/30"
                >
                  <Link to={`/inmueble/${f.id}`} className="absolute inset-0 rounded-lg" aria-label={f.titulo || "Ficha"} />
                  <div className="pointer-events-none">
                    <div className="text-fg text-[15px] leading-snug line-clamp-2">
                      {f.titulo || "(sin título)"}
                    </div>
                    <div className="text-xs text-faint mt-0.5">
                      {[f.ciudad, f.pais].filter(Boolean).join(" · ") || "—"}
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-3 border-t border-line/70 pt-2">
                      <span className="cifra text-fg text-sm">{fmtDinero(f.precio, f.moneda)}</span>
                      <span className="cifra text-faint text-sm">
                        {f.superficie_util_m2 || f.superficie_construida_m2
                          ? `${fmtNum(f.superficie_util_m2 || f.superficie_construida_m2)} m²`
                          : "—"}
                      </span>
                    </div>
                  </div>
                  <div className="relative mt-2 flex items-center gap-1.5 flex-wrap">
                    <span className="pointer-events-none"><BadgeCalidad estado={f.estado_calidad} /></span>
                    {f.tiene_confotur === true && <BadgeConfotur />}
                    {f.url_anuncio && (
                      <a
                        href={f.url_anuncio} target="_blank" rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-[11px] text-accent hover:underline ml-auto"
                      >
                        Ver anuncio
                      </a>
                    )}
                  </div>
                </li>
              ))}
            </ul>

            {/* Escritorio: tabla densa */}
            <div className="hidden lg:block overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Inmueble</th>
                    <th className="text-right">Precio</th>
                    <th className="text-right">m²</th>
                    <th>Estado del dato</th>
                    <th className="text-right">Anuncio</th>
                  </tr>
                </thead>
                <tbody className="escalonado">
                  {filas.map((f, i) => (
                    <tr key={f.id} {...paso(i)} className="group">
                      <td className="max-w-md">
                        <Link className="text-fg group-hover:text-accent transition-colors truncate block" to={`/inmueble/${f.id}`}>
                          {f.titulo || "(sin título)"}
                        </Link>
                        <span className="text-xs text-faint">
                          {[f.ciudad, f.pais].filter(Boolean).join(" · ") || "—"}
                        </span>
                      </td>
                      <td className="text-right cifra text-fg whitespace-nowrap">{fmtDinero(f.precio, f.moneda)}</td>
                      <td className="text-right cifra text-faint">
                        {f.superficie_util_m2 || f.superficie_construida_m2
                          ? fmtNum(f.superficie_util_m2 || f.superficie_construida_m2)
                          : "—"}
                      </td>
                      <td>
                        <div className="flex items-center gap-1.5">
                          <BadgeCalidad estado={f.estado_calidad} />
                          {f.tiene_confotur === true && <BadgeConfotur />}
                        </div>
                      </td>
                      <td className="text-right">
                        {f.url_anuncio ? (
                          <a href={f.url_anuncio} target="_blank" rel="noreferrer" className="text-[13px] text-accent hover:underline">
                            Abrir
                          </a>
                        ) : <span className="text-faint">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
