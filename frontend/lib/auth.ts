import jwt from 'jsonwebtoken';
import { getCookie, setCookie, deleteCookie } from 'cookies-next';
import { NextApiRequest, NextApiResponse } from 'next';

const JWT_SECRET = process.env.JWT_SECRET || 'change-this-secret-key';
const AUTH_PASSWORD = process.env.AUTH_PASSWORD || 'comfyui123';

export interface AuthToken {
  authenticated: boolean;
  timestamp: number;
}

export function createToken(): string {
  const payload: AuthToken = {
    authenticated: true,
    timestamp: Date.now(),
  };
  return jwt.sign(payload, JWT_SECRET, { expiresIn: '24h' });
}

export function verifyToken(token: string): AuthToken | null {
  try {
    return jwt.verify(token, JWT_SECRET) as AuthToken;
  } catch {
    return null;
  }
}

export function checkAuth(req: NextApiRequest, res: NextApiResponse): boolean {
  const token = getCookie('auth-token', { req, res }) as string;
  if (!token) return false;
  
  const payload = verifyToken(token);
  return payload !== null && payload.authenticated;
}

export function login(password: string, res: NextApiResponse): boolean {
  if (password === AUTH_PASSWORD) {
    const token = createToken();
    setCookie('auth-token', token, {
      res,
      maxAge: 60 * 60 * 24, // 24 hours
      httpOnly: true,
      sameSite: 'lax', // Changed from 'strict' to 'lax' for reverse proxy compatibility
      secure: false, // Disable secure for now since we're behind reverse proxy
      path: '/', // Explicitly set path
    });
    return true;
  }
  return false;
}

export function logout(res: NextApiResponse): void {
  deleteCookie('auth-token', { 
    res,
    path: '/', // Match the path used when setting the cookie
  });
}

// Alternative auth check that supports both cookies and headers
export function checkAuthFlex(req: NextApiRequest, res: NextApiResponse): boolean {
  // First try header-based auth
  const authHeader = req.headers.authorization;
  const customHeader = req.headers['x-auth-token'] as string;
  
  let token = null;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    token = authHeader.substring(7);
  } else if (customHeader) {
    token = customHeader;
  }

  if (token) {
    const payload = verifyToken(token);
    return payload !== null && payload.authenticated;
  }

  // Fallback to cookie-based auth
  return checkAuth(req, res);
}