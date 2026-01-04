import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import client from '../api/client';

export default function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const token = searchParams.get('token');

    if (token) {
      // Set the cookie via API call (avoids cross-site cookie blocking)
      client.post('/auth/set-cookie', null, { params: { token } })
        .then(() => {
          // Cookie is now set, redirect to dashboard
          navigate('/', { replace: true });
        })
        .catch(() => {
          // If setting cookie fails, redirect to login
          navigate('/login', { replace: true });
        });
    } else {
      // No token, redirect to login
      navigate('/login', { replace: true });
    }
  }, [navigate, searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Signing you in...</p>
      </div>
    </div>
  );
}
