import { Route, Routes } from "react-router-dom";
import { NavBar } from "../components/navigation/NavBar";
import { HomePage } from "../pages/home/HomePage";
import { AnimeDetailPage } from "../pages/anime/AnimeDetailPage";
import { WatchPage } from "../pages/watch/WatchPage";
import { SearchPage } from "../pages/search/SearchPage";
import { ProfilePage } from "../pages/profile/ProfilePage";
import { FavoritesPage } from "../pages/favorites/FavoritesPage";
import { ForgotPasswordPage } from "../pages/forgot-password/ForgotPasswordPage";
import { ResetPasswordPage } from "../pages/reset-password/ResetPasswordPage";
import { VerifyEmailPage } from "../pages/verify-email/VerifyEmailPage";

function App() {
  return (
    <>
      <NavBar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/anime/:slug" element={<AnimeDetailPage />} />
        <Route path="/watch/:episodeId" element={<WatchPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
      </Routes>
    </>
  );
}

export default App;
