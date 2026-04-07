import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import { AppProviders } from "./contexts/AppProviders";
import { initFrontendObservability } from "./observability/client";
import "./index.css";

initFrontendObservability();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProviders>
      <App />
    </AppProviders>
  </React.StrictMode>,
);
