import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import LogsPage from "./pages/LogsPage";
import OptimizePage from "./pages/OptimizePage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/optimize" replace />} />
          <Route path="logs" element={<LogsPage />} />
          <Route path="optimize" element={<OptimizePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
