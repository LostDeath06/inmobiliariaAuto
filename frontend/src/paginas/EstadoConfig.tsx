import { useEffect, useState } from "react";
import { api } from "../api";
import { AvisoRiesgo, Card, Chip, Esqueleto, paso } from "../ui";

export default function EstadoConfig() {
  const [estados, setEstados] = useState<any[]>([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    api.get("/api/config/estado-pais").then(setEstados).catch(() => {}).finally(() => setCargando(false));
  }, []);

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted max-w-2xl">
        Checklist de qué falta para que cada país sea operativo. Ningún país arranca
        hasta cargar sus datos: es el comportamiento correcto, no un fallo.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-start escalonado">
        {cargando &&
          [0, 1, 2].map((i) => (
            <div key={i} className="rounded-lg border border-line bg-surface shadow-elev-1 overflow-hidden" aria-busy="true">
              <div className="h-11 border-b border-line flex items-center justify-between px-4">
                <Esqueleto className="h-3.5 w-8" />
                <Esqueleto className="h-4 w-24" />
              </div>
              <div className="p-4 space-y-3">
                {[0, 1, 2, 3, 4, 5].map((j) => (
                  <div key={j} className="flex gap-2.5">
                    <Esqueleto className="h-1.5 w-1.5 rounded-full mt-1.5 shrink-0" />
                    <div className="flex-1 space-y-1">
                      <Esqueleto className="h-3.5 w-32" />
                      <Esqueleto className="h-3 w-24" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        {estados.map((e, idx) => {
          // Una advertencia manda sobre "faltan datos": no es un hueco que se vea,
          // es un score que sale igualmente y mal calibrado.
          const conAdvertencia = e.items.some((it: any) => it.advertencia);
          return (
            <div key={e.pais} {...paso(idx)}>
            <Card
              titulo={e.pais}
              acciones={
                conAdvertencia ? <Chip tono="danger">Calibración incompleta</Chip>
                  : e.operativo ? <Chip tono="positive">Operativo</Chip>
                    : <Chip tono="warning">Faltan datos</Chip>
              }
            >
              <ul className="space-y-2">
                {e.items.map((it: any) => (
                  <li key={it.clave}>
                    <div className="flex items-start gap-2.5">
                      <span className={`mt-1.5 h-1.5 w-1.5 rounded-full shrink-0 ${
                        it.ok ? "bg-positive" : it.advertencia ? "bg-danger" : "bg-faint"
                      }`} />
                      <div className="min-w-0">
                        <span className="text-sm text-fg font-medium">{it.clave}</span>
                        {it.provisional && (
                          <span className="ml-2 text-[10px] font-semibold uppercase tracking-wide text-warning">Provisional</span>
                        )}
                        <div className="text-xs text-muted">{it.detalle}</div>
                      </div>
                    </div>
                    {it.advertencia && (
                      <div className="mt-1.5 ml-4">
                        <AvisoRiesgo>{it.advertencia}</AvisoRiesgo>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
            </div>
          );
        })}
      </div>
    </div>
  );
}
