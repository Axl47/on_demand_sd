import { NextApiRequest, NextApiResponse } from 'next';
import { checkAuth } from '@/lib/auth';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const isAuthenticated = checkAuth(req, res);
  return res.status(200).json({ authenticated: isAuthenticated });
}