import { NextApiRequest, NextApiResponse } from 'next';
import { verifyToken } from '@/lib/auth';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  // Check for token in Authorization header or x-auth-token header
  const authHeader = req.headers.authorization;
  const customHeader = req.headers['x-auth-token'] as string;
  
  let token = null;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    token = authHeader.substring(7);
  } else if (customHeader) {
    token = customHeader;
  }

  console.log('Auth check (alt) - authorization header:', authHeader ? '[PRESENT]' : '[MISSING]');
  console.log('Auth check (alt) - x-auth-token header:', customHeader ? '[PRESENT]' : '[MISSING]');
  console.log('Auth check (alt) - extracted token:', token ? '[PRESENT]' : '[MISSING]');

  if (!token) {
    return res.status(200).json({ 
      authenticated: false,
      debug: {
        hasAuthHeader: !!authHeader,
        hasCustomHeader: !!customHeader,
        message: 'No token found in headers'
      }
    });
  }

  const payload = verifyToken(token);
  const isAuthenticated = payload !== null && payload.authenticated;
  
  console.log('Auth check (alt) result:', isAuthenticated);

  return res.status(200).json({ 
    authenticated: isAuthenticated,
    debug: {
      hasAuthHeader: !!authHeader,
      hasCustomHeader: !!customHeader,
      tokenValid: isAuthenticated
    }
  });
}