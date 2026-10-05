import { NavLink } from "react-router-dom";
import { useAuth } from "../../features/auth/useAuth";

export function NavBar() {
  const { user, isLoading } = useAuth();

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <NavLink to="/" className="wordmark">
          Anime<span>Platform</span>
        </NavLink>
        <ul className="nav-links">
          <li>
            <NavLink to="/" end>
              Home
            </NavLink>
          </li>
          <li>
            <NavLink to="/search">Search</NavLink>
          </li>
          <li>
            <NavLink to="/favorites">Favorites</NavLink>
          </li>
          {!isLoading && (
            <li>
              <NavLink to="/profile">
                {user ? (user.display_name ?? user.email) : "Sign in"}
              </NavLink>
            </li>
          )}
        </ul>
      </div>
    </nav>
  );
}
