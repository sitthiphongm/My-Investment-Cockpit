import { Outlet } from 'react-router-dom';
import NavigationMenu from './NavigationMenu';

export default function Layout() {
  return (
    <div className="app-layout">
      <NavigationMenu />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
