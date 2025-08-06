import { NextApiRequest, NextApiResponse } from 'next';
import { checkAuth } from '@/lib/auth';
import { getCookie } from 'cookies-next';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const token = getCookie('auth-token', { req, res });
  console.log('Auth check - cookies received:', req.headers.cookie);
  console.log('Auth check - auth-token extracted:', token ? '[PRESENT]' : '[MISSING]');
  
  const isAuthenticated = checkAuth(req, res);
  console.log('Auth check result:', isAuthenticated);
  
  return res.status(200).json({ 
    authenticated: isAuthenticated, 
    debug: {
      hasToken: !!token,
      cookieHeader: !!req.headers.cookie
    }
  });
}