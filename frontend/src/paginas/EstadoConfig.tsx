import { useEffect, useState } from "react";
import { api } from "../api";
import { AvisoRiesgo, Card, Chip, Vacio } from "../ui";

export default function EstadoConfig() {
  const [estados, setEstados] = useState<any[]>([]);

  useEffect(() => { api.get("/api/config/estado-pais").then(setEstados).catch(() => {}); }, []);

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted max-w-2xl">
        Checklist de qué falta para que cada país sea operativo. Ningún país arranca
        hasta cargar sus datos: es el comportamiento correcto, no un fallo.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-start">
        {estados.map((e) => {
          // Una advertencia manda sobre "faltan datos": no es un hueco que se vea,
          // es un score que sale igualmente y mal calibrado.
          const conAdvertencia = e.items.some((it: any) => it.advertencia);
          return (
            <Card
              key={e.pais}
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
          );
        })}
        {estados.length === 0 && <Vacio>Cargando estado por país…</Vacio>}
      </div>
    </div>
  );
}
