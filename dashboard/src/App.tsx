import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Overview } from "./pages/Overview";
import { Traces } from "./pages/Traces";
import { TraceDetailPage } from "./pages/TraceDetailPage";
import { Alerts } from "./pages/Alerts";
import { Prompts } from "./pages/Prompts";

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/traces" element={<Traces />} />
          <Route path="/traces/:id" element={<TraceDetailPage />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/prompts" element={<Prompts />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
