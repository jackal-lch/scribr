import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import client, { API_URL, getToken, removeToken } from '../api/client';

interface User {
  id: string;
  email: string;
  name: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if we have a token, then validate it
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }

    client.get('/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => {
        removeToken(); // Token invalid, remove it
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = () => {
    window.location.href = `${API_URL}/auth/google`;
  };

  const logout = () => {
    removeToken();
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
