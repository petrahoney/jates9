import React from "react";
import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navigation from "./components/Navigation";
import LandingPage from "./pages/LandingPage";
import HealthQuiz from "./pages/HealthQuiz";
import Challenge from "./pages/Challenge";
import ProductPage from "./pages/ProductPage";
import AIChat from "./pages/AIChat";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Navigation />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/quiz" element={<HealthQuiz />} />
          <Route path="/challenge" element={<Challenge />} />
          <Route path="/product" element={<ProductPage />} />
          <Route path="/chat" element={<AIChat />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
