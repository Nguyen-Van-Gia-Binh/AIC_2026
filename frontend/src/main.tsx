import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
// Be Vietnam Pro — font sans duy nhat cho toan bo UI (tieu de + noi dung). Package @fontsource
// dong goi san woff2/woff (subset vietnamese + latin), Vite bundle thanh asset -> chay offline,
// khong phu thuoc Google Fonts CDN. Thay cho Caprasimo (thieu dau tieng Viet) + Figtree.
import "@fontsource/be-vietnam-pro/400.css";
import "@fontsource/be-vietnam-pro/500.css";
import "@fontsource/be-vietnam-pro/600.css";
import "@fontsource/be-vietnam-pro/700.css";
import "./styles/organic.css";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
