// `??` y no `||`: en producción VITE_API_URL se compila VACÍA a propósito, para que
// las llamadas salgan relativas (/api/...) al mismo origen y las sirva el proxy de
// nginx. Con `||`, la cadena vacía es falsy y caería de vuelta a localhost:8000,
// que en el VPS no existe desde el navegador del usuario.
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function req(metodo: string, ruta: string, cuerpo?: unknown) {
  const opciones: RequestInit = {
    method: metodo,
    headers: { "Content-Type": "application/json" },
  };
  if (cuerpo !== undefined) opciones.body = JSON.stringify(cuerpo);
  const resp = await fetch(`${BASE}${ruta}`, opciones);
  if (!resp.ok) {
    const texto = await resp.text();
    throw new Error(`${resp.status}: ${texto}`);
  }
  const ct = resp.headers.get("content-type") || "";
  return ct.includes("application/json") ? resp.json() : resp.text();
}

export const api = {
  get: (r: string) => req("GET", r),
  post: (r: string, b?: unknown) => req("POST", r, b),
  put: (r: string, b?: unknown) => req("PUT", r, b),
  del: (r: string) => req("DELETE", r),
};

export const PAISES = ["ES", "DO", "VE"];
