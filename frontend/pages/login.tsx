import { useState } from 'react';
import { useRouter } from 'next/router';
import axios from 'axios';
import { setAuthToken } from '@/lib/auth-client';

export default function Login() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Try the alternative login method first
      const response = await axios.post('/api/auth/login-alt', { password });
      console.log('Login response (alt):', response.data);
      
      if (response.data.token) {
        // Store token in localStorage
        setAuthToken(response.data.token);
        console.log('Token stored in localStorage');
        
        // Force a hard redirect
        window.location.href = '/';
      } else {
        setError('Login failed - no token received');
      }
    } catch (err: any) {
      console.error('Login error (alt):', err);
      
      // Fallback to cookie-based login
      try {
        const fallbackResponse = await axios.post('/api/auth/login', { password });
        console.log('Fallback login response:', fallbackResponse.data);
        window.location.href = '/';
      } catch (fallbackErr: any) {
        console.error('Fallback login error:', fallbackErr);
        setError(fallbackErr.response?.data?.error || 'Login failed');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900">
      <div className="bg-gray-800 p-8 rounded-lg shadow-xl w-full max-w-md">
        <h1 className="text-2xl font-bold text-white mb-6 text-center">
          ComfyUI Controller
        </h1>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter password"
              required
              disabled={loading}
            />
          </div>

          {error && (
            <div className="text-red-400 text-sm text-center">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold rounded-md transition duration-200"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
}