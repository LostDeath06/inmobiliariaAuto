import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import "./index.css";
import { ProveedorTema } from "./tema";
import ConfigMercado from "./paginas/ConfigMercado";
import Costes from "./paginas/Costes";
import EstadoConfig from "./paginas/EstadoConfig";
import Ficha from "./paginas/Ficha";
import Inventario from "./paginas/Inventario";
import Jobs from "./paginas/Jobs";
import Perfiles from "./paginas/Perfiles";
import Portales from "./paginas/Portales";
import Ranking from "./paginas/Ranking";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Ranking /> },
      { path: "inventario", element: <Inventario /> },
      { path: "costes", element: <Costes /> },
      { path: "inmueble/:id", element: <Ficha /> },
      { path: "perfiles", element: <Perfiles /> },
      { path: "mercado", element: <ConfigMercado /> },
      { path: "estado", element: <EstadoConfig /> },
      { path: "portales", element: <Portales /> },
      { path: "jobs", element: <Jobs /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ProveedorTema>
      <RouterProvider router={router} />
    </ProveedorTema>
  </React.StrictMode>
);
