import { Route, Routes } from "react-router-dom";
import { NavBar } from "../components/navigation/NavBar";
import { HomePage } from "../pages/home/HomePage";
import { AnimeDetailPage } from "../pages/anime/AnimeDetailPage";
import { WatchPage } from "../pages/watch/WatchPage";
import { SearchPage } from "../pages/search/SearchPage";
import { ProfilePage } from "../pages/profile/ProfilePage";
import { FavoritesPage } from "../pages/favorites/FavoritesPage";

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
      </Routes>
    </>
  );
}

export default App;
