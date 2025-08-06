import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/router';
import axios from 'axios';
import api from '@/lib/api';
import { getAuthToken, isTokenExpired, clearAuthToken } from '@/lib/auth-client';
import { formatWithTimezone } from '@/lib/time-utils';

interface InstanceStatus {
  status: 'RUNNING' | 'TERMINATED' | 'STOPPING' | 'PROVISIONING' | 'STAGING' | 'UNKNOWN';
  external_ip?: string;
  comfyui_url?: string;
  last_activity?: string;
}

export default function Home() {
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [instanceStatus, setInstanceStatus] = useState<InstanceStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const keepAliveIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const statusCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Check authentication
  useEffect(() => {
    checkAuth();
  }, []);

  // Check instance status periodically
  useEffect(() => {
    if (authenticated) {
      checkInstanceStatus();
      statusCheckIntervalRef.current = setInterval(checkInstanceStatus, 10000); // Every 10 seconds
    }

    return () => {
      if (statusCheckIntervalRef.current) {
        clearInterval(statusCheckIntervalRef.current);
      }
    };
  }, [authenticated]);

  // Send keep-alive when instance is running
  useEffect(() => {
    if (instanceStatus?.status === 'RUNNING') {
      sendKeepAlive();
      keepAliveIntervalRef.current = setInterval(sendKeepAlive, 30000); // Every 30 seconds
    } else {
      if (keepAliveIntervalRef.current) {
        clearInterval(keepAliveIntervalRef.current);
        keepAliveIntervalRef.current = null;
      }
    }

    return () => {
      if (keepAliveIntervalRef.current) {
        clearInterval(keepAliveIntervalRef.current);
      }
    };
  }, [instanceStatus?.status]);

  const checkAuth = async () => {
    try {
      // First check localStorage token
      const token = getAuthToken();
      console.log('Checking auth - token from localStorage:', token ? '[PRESENT]' : '[MISSING]');
      
      if (!token) {
        console.log('No token in localStorage, redirecting to login');
        router.push('/login');
        return;
      }
      
      if (isTokenExpired(token)) {
        console.log('Token expired, clearing and redirecting to login');
        clearAuthToken();
        router.push('/login');
        return;
      }
      
      // Verify token with server using alternative endpoint
      const res = await axios.get('/api/auth/check-alt', {
        headers: {
          'x-auth-token': token
        }
      });
      
      console.log('Auth check response:', res.data);
      
      if (!res.data.authenticated) {
        console.log('Server says token invalid, clearing and redirecting');
        clearAuthToken();
        router.push('/login');
      } else {
        console.log('Authentication successful');
        setAuthenticated(true);
      }
    } catch (err) {
      console.error('Auth check failed:', err);
      clearAuthToken();
      router.push('/login');
    }
  };

  const checkInstanceStatus = async () => {
    try {
      const res = await api.get('/api/instance/status');
      console.log('Raw API response:', res);
      console.log('Response data:', JSON.stringify(res.data, null, 2));
      setInstanceStatus(res.data);
      setError('');
    } catch (err) {
      console.error('Failed to check instance status:', err);
      setError('Failed to check instance status');
    }
  };

  const sendKeepAlive = async () => {
    try {
      await api.post('/api/instance/keep-alive');
    } catch (err) {
      console.error('Failed to send keep-alive:', err);
    }
  };

  const startInstance = async () => {
    setLoading(true);
    setError('');
    try {
      await api.post('/api/instance/start');
      await checkInstanceStatus();
    } catch (err: any) {
      const errorMessage = err.response?.data?.error || 'Failed to start instance';
      const statusCode = err.response?.status;
      
      // Add helpful context for 503 Service Unavailable (resource exhaustion)
      if (statusCode === 503) {
        setError(`${errorMessage} 🔄 This is temporary - GPU resources are limited on Google Cloud.`);
      } else {
        setError(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  const stopInstance = async () => {
    setLoading(true);
    setError('');
    try {
      await api.post('/api/instance/stop');
      await checkInstanceStatus();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to stop instance');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    clearAuthToken();
    router.push('/login');
  };

  if (authenticated === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-white text-xl">Loading...</div>
      </div>
    );
  }

  const comfyuiUrl = instanceStatus?.comfyui_url || 'https://comfy.axorai.net';

  const isRunning = instanceStatus?.status === 'RUNNING';
  const isTransitioning = ['STOPPING', 'PROVISIONING', 'STAGING'].includes(instanceStatus?.status || '');

  // Debug logging
  console.log('Instance Status:', instanceStatus);
  console.log('ComfyUI URL:', comfyuiUrl);
  console.log('Is Running:', isRunning);
  console.log('Should show iframe:', isRunning && comfyuiUrl);

  return (
    <div className="min-h-screen bg-gray-900 relative">
      {/* Control Panel */}
      <div className="absolute top-0 left-0 right-0 bg-gray-800 shadow-lg z-10 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h1 className="text-xl font-bold text-white">ComfyUI Controller</h1>
            
            <div className="flex items-center space-x-2">
              <span className="text-gray-400">Status:</span>
              <span className={`font-semibold ${
                isRunning ? 'text-green-400' : 
                isTransitioning ? 'text-yellow-400' : 
                'text-red-400'
              }`}>
                {instanceStatus?.status || 'UNKNOWN'}
              </span>
            </div>

            {instanceStatus?.last_activity && (
              <div className="text-sm text-gray-400">
                Last activity: {formatWithTimezone(instanceStatus.last_activity)}
              </div>
            )}
          </div>

          <div className="flex items-center space-x-4">
            {isRunning ? (
              <button
                onClick={stopInstance}
                disabled={loading || isTransitioning}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold rounded-md transition duration-200"
              >
                {loading ? 'Processing...' : 'Stop Instance'}
              </button>
            ) : (
              <button
                onClick={startInstance}
                disabled={loading || isTransitioning}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold rounded-md transition duration-200"
              >
                {loading ? 'Processing...' : 'Start Instance'}
              </button>
            )}

            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white font-semibold rounded-md transition duration-200"
            >
              Logout
            </button>
          </div>
        </div>

        {error && (
          <div className="max-w-7xl mx-auto mt-2">
            <div className="text-red-400 text-sm">{error}</div>
          </div>
        )}
      </div>

      {/* ComfyUI iframe or Start Message */}
      <div className="pt-20 h-screen">
        {isRunning && comfyuiUrl ? (
          <div className="w-full h-full">
            <iframe
              src={comfyuiUrl}
              className="w-full h-full border-0"
              title="ComfyUI"
              sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
              onLoad={() => console.log('Iframe loaded successfully')}
              onError={(e) => console.error('Iframe error:', e)}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              {isTransitioning ? (
                <>
                  <div className="text-white text-2xl mb-4">
                    Instance is {instanceStatus?.status?.toLowerCase()}...
                  </div>
                  <div className="text-gray-400">
                    Please wait, this may take a few minutes
                  </div>
                </>
              ) : (
                <>
                  <div className="text-white text-2xl mb-4">
                    ComfyUI instance is not running
                  </div>
                  <button
                    onClick={startInstance}
                    disabled={loading}
                    className="px-6 py-3 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold rounded-md transition duration-200"
                  >
                    {loading ? 'Starting...' : 'Start ComfyUI'}
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}